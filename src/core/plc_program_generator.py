"""
PLC Program Generator - Generates IEC 61131-3 Structured Text programs for IED devices.

For each IED instantiated as an IEC 61850 server, this module generates a corresponding
PLC program that can:
- Access IED data points
- Execute cyclic logic
- Be edited by users
- Persist and reload with the project
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class PLCProgramMetadata:
    """Metadata for a generated PLC program."""
    device_name: str
    ied_name: str
    program_name: str
    file_path: str
    created: datetime
    modified: datetime
    cycle_time_ms: int = 100  # Default 100ms cycle time
    enabled: bool = True


class PLCProgramGenerator:
    """
    Generates PLC program templates for IEC 61850 devices.
    
    Each program follows IEC 61131-3 Structured Text (ST) syntax and includes:
    - Program header with metadata
    - Variable declarations
    - Initialization section
    - Main cyclic execution block
    - User-editable logic sections
    """
    
    def __init__(self, programs_dir: str = "plc_programs"):
        """
        Initialize PLC program generator.
        
        Args:
            programs_dir: Directory to store generated PLC programs
        """
        self.programs_dir = Path(programs_dir)
        self.programs_dir.mkdir(exist_ok=True, parents=True)
        
    def generate_program_for_ied(self, 
                                  ied_name: str, 
                                  device_name: str,
                                  logical_devices: List[str] = None) -> PLCProgramMetadata:
        """
        Generate a PLC program template for an IED.
        
        Args:
            ied_name: Name of IED from SCD
            device_name: Device name in application
            logical_devices: List of logical device instances
            
        Returns:
            PLCProgramMetadata with program information
        """
        program_name = f"PRG_{device_name.replace(' ', '_')}"
        file_path = self.programs_dir / f"{program_name}.st"
        
        # Generate program content
        content = self._generate_st_program(
            ied_name=ied_name,
            device_name=device_name,
            program_name=program_name,
            logical_devices=logical_devices or []
        )
        
        # Write program file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        logger.info(f"Generated PLC program: {file_path}")
        
        now = datetime.now()
        return PLCProgramMetadata(
            device_name=device_name,
            ied_name=ied_name,
            program_name=program_name,
            file_path=str(file_path),
            created=now,
            modified=now,
            cycle_time_ms=100,
            enabled=True
        )
        
    def _generate_st_program(self, 
                             ied_name: str, 
                             device_name: str,
                             program_name: str,
                             logical_devices: List[str]) -> str:
        """
        Generate Structured Text program content.
        
        Returns:
            Complete ST program as string
        """
        template = f'''(* ========================================================================
   PLC PROGRAM: {program_name}
   IED: {ied_name}
   Device: {device_name}
   Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
   
   This program runs cyclically (default 100ms) and has access to all
   data points of the associated IEC 61850 device. Users can add custom
   logic in the designated sections below.
   ======================================================================== *)

PROGRAM {program_name}
VAR
    (* ====== System Variables ====== *)
    cycle_count: UDINT := 0;           (* Increments each scan cycle *)
    first_scan: BOOL := TRUE;          (* TRUE only on first execution *)
    scan_time_ms: REAL := 0.0;         (* Last scan time in milliseconds *)
    
    (* ====== IED Connection Status ====== *)
    ied_connected: BOOL := FALSE;      (* TRUE when IED server is running *)
    ied_name: STRING := '{ied_name}';
    device_name: STRING := '{device_name}';
    
    (* ====== Logical Devices ====== *)
    (* Available LDs: {', '.join(logical_devices) if logical_devices else 'None'} *)
    
    (* ====== User Variables ====== *)
    (* Add your custom variables here *)
    (* Example:
    timer1: TON;
    counter: INT := 0;
    status_word: WORD;
    *)
    
END_VAR

(* ======================================================================
   INITIALIZATION SECTION
   Runs once on first scan. Use for setup and initialization.
   ====================================================================== *)
IF first_scan THEN
    (* Initialize user variables here *)
    cycle_count := 0;
    
    (* Log program start *)
    (* SCADA_LOG('INFO', CONCAT('PLC Program started: ', device_name)); *)
    
    first_scan := FALSE;
END_IF;

(* ======================================================================
   MAIN CYCLIC EXECUTION
   This section runs continuously every scan cycle (default 100ms).
   ====================================================================== *)

(* Increment cycle counter *)
cycle_count := cycle_count + 1;

(* ====== USER LOGIC SECTION 1: Pre-Processing ====== *)
(* Add logic that should run before main processing *)
(* Example:
IF ied_connected THEN
    (* Read IED data points *)
    (* status_word := READ_IED_DATA(device_name, 'LD0/MMXU1$MX$TotW$mag'); *)
END_IF;
*)


(* ====== USER LOGIC SECTION 2: Main Processing ====== *)
(* Add your main control logic here *)
(* Example:
IF counter > 100 THEN
    counter := 0;
    (* Perform periodic action *)
END_IF;
counter := counter + 1;
*)


(* ====== USER LOGIC SECTION 3: Post-Processing ====== *)
(* Add logic for outputs, writes, and cleanup *)
(* Example:
IF ied_connected THEN
    (* Write control commands to IED *)
    (* WRITE_IED_CONTROL(device_name, 'LD0/CSWI1$CO$Pos', TRUE); *)
END_IF;
*)

(* ====== Built-in Functions Available ====== *)
(* 
   READ_IED_DATA(device: STRING, ref: STRING): ANY
       - Read data from IED object reference
       - Example: READ_IED_DATA('MyIED', 'LD0/MMXU1$MX$TotW$mag')
       
   WRITE_IED_DATA(device: STRING, ref: STRING, value: ANY): BOOL
       - Write data to IED object reference
       - Returns TRUE on success
       
   WRITE_IED_CONTROL(device: STRING, ref: STRING, value: ANY): BOOL
       - Send control command to IED
       - Returns TRUE on success
       
   SCADA_LOG(level: STRING, message: STRING)
       - Log message to event log
       - Levels: 'INFO', 'WARNING', 'ERROR'
       
   GET_DEVICE_STATUS(device: STRING): BOOL
       - Check if device is connected
*)

END_PROGRAM
'''
        return template
        
    def load_program(self, file_path: str) -> tuple[str, str]:
        """
        Load existing PLC program from file.
        
        Args:
            file_path: Path to .st file
            
        Returns:
            Tuple of (program_name, content)
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Program file not found: {file_path}")
            
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Extract program name from PROGRAM declaration
        program_name = path.stem
        for line in content.split('\n'):
            if line.strip().startswith('PROGRAM '):
                parts = line.split()
                if len(parts) >= 2:
                    program_name = parts[1]
                    break
                    
        return program_name, content
        
    def save_program(self, file_path: str, content: str) -> bool:
        """
        Save PLC program content to file.
        
        Args:
            file_path: Path to .st file
            content: Program content
            
        Returns:
            True on success
        """
        try:
            path = Path(file_path)
            path.parent.mkdir(exist_ok=True, parents=True)
            
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            logger.info(f"Saved PLC program: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save program: {e}")
            return False
            
    def get_all_programs(self) -> List[Path]:
        """
        Get list of all PLC program files.
        
        Returns:
            List of Path objects for .st files
        """
        return list(self.programs_dir.glob("*.st"))
