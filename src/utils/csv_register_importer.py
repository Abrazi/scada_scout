"""CSV Register Importer for Modbus Servers
Imports register definitions from Gen_Registers.csv format and configures
Modbus Slave Servers with proper register blocks and mappings.

Supported CSV formats:
1. Triangle MicroWorks format: IsEnabled,Index,PointType,Name,Description,Direction,Value,Quality
2. Extended format: IsEnabled,Index,PointType,Name,Description,Direction,Value,Quality,DataType,Endianness,Scale,Offset

Point Types:
1 = Coil (0x, read/write)
2 = Discrete Input (1x, read-only)
3 = Input Register (3x, read-only)
4 = Holding Register (4x, read/write)
"""

import csv
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

from src.models.device_models import (
    SlaveRegisterBlock,
    ModbusSignalMapping,
    ModbusDataType,
    ModbusEndianness
)

logger = logging.getLogger(__name__)


@dataclass
class RegisterDefinition:
    """Parsed register definition from CSV"""
    index: int
    point_type: int  # 1=coil, 2=discrete, 3=input_reg, 4=holding_reg
    name: str
    description: str = ""
    direction: str = "None"  # Input/Output/None
    default_value: int = 0
    default_quality: int = 0
    data_type: ModbusDataType = ModbusDataType.UINT16
    endianness: ModbusEndianness = ModbusEndianness.BIG_ENDIAN
    scale: float = 1.0
    offset: float = 0.0
    enabled: bool = True


class CSVRegisterImporter:
    """Imports and manages register definitions from CSV files"""
    
    # Point type to register type mapping
    POINT_TYPE_MAP = {
        1: "coils",          # Coils (0x)
        2: "discrete",       # Discrete Inputs (1x)
        3: "input",          # Input Registers (3x)
        4: "holding"         # Holding Registers (4x)
    }
    
    # Point type to Modbus address offset
    ADDRESS_OFFSET_MAP = {
        1: 0,      # Coils: 0-9999
        2: 10000,  # Discrete: 10000-19999
        3: 30000,  # Input Registers: 30000-39999
        4: 40000   # Holding Registers: 40000-49999
    }
    
    def __init__(self):
        self.registers: List[RegisterDefinition] = []
        
    def parse_csv(self, csv_path: str) -> bool:
        """Parse CSV file and extract register definitions
        
        Args:
            csv_path: Path to CSV file
            
        Returns:
            True if successful, False otherwise
        """
        self.registers.clear()
        
        if not Path(csv_path).exists():
            logger.error(f"CSV file not found: {csv_path}")
            return False
        
        try:
            with open(csv_path, 'r', encoding='utf-8-sig') as f:  # Handle BOM
                reader = csv.DictReader(f)
                
                # Validate required columns
                required_cols = {'Index', 'PointType', 'Name'}
                if not required_cols.issubset(set(reader.fieldnames or [])):
                    logger.error(f"CSV missing required columns: {required_cols}")
                    return False
                
                for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is 1)
                    try:
                        reg = self._parse_row(row)
                        if reg and reg.enabled:
                            self.registers.append(reg)
                    except Exception as e:
                        logger.warning(f"Error parsing row {row_num}: {e}")
                        continue
            
            logger.info(f"Loaded {len(self.registers)} register definitions from {csv_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to parse CSV {csv_path}: {e}")
            return False
    
    def _parse_row(self, row: Dict[str, str]) -> Optional[RegisterDefinition]:
        """Parse a single CSV row into RegisterDefinition"""
        
        # Check if enabled
        enabled_str = row.get('IsEnabled', 'True').strip()
        enabled = enabled_str.lower() in ['true', '1', 'yes', 'y']
        
        if not enabled:
            return None
        
        # Required fields
        index = int(row['Index'])
        point_type = int(row['PointType'])
        name = row['Name'].strip()
        
        # Optional fields
        description = row.get('Description', '').strip()
        direction = row.get('Direction', 'None').strip()
        
        # Default values
        default_value = 0
        value_str = row.get('Value', '0').strip()
        if value_str:
            try:
                default_value = int(value_str)
            except ValueError:
                try:
                    default_value = int(float(value_str))
                except ValueError:
                    pass
        
        default_quality = 0
        quality_str = row.get('Quality', '0').strip()
        if quality_str:
            try:
                default_quality = int(quality_str)
            except ValueError:
                pass
        
        # Extended format support (DataType, Endianness, Scale, Offset)
        data_type = ModbusDataType.UINT16
        data_type_str = row.get('DataType', '').strip()
        if data_type_str:
            for dt in ModbusDataType:
                if dt.value == data_type_str or dt.name == data_type_str.upper():
                    data_type = dt
                    break
        
        endianness = ModbusEndianness.BIG_ENDIAN
        endianness_str = row.get('Endianness', '').strip()
        if endianness_str:
            for en in ModbusEndianness:
                if en.value == endianness_str or en.name == endianness_str.upper():
                    endianness = en
                    break
        
        scale = 1.0
        scale_str = row.get('Scale', '').strip()
        if scale_str:
            try:
                scale = float(scale_str)
            except ValueError:
                pass
        
        offset = 0.0
        offset_str = row.get('Offset', '').strip()
        if offset_str:
            try:
                offset = float(offset_str)
            except ValueError:
                pass
        
        return RegisterDefinition(
            index=index,
            point_type=point_type,
            name=name,
            description=description,
            direction=direction,
            default_value=default_value,
            default_quality=default_quality,
            data_type=data_type,
            endianness=endianness,
            scale=scale,
            offset=offset,
            enabled=enabled
        )
    
    def generate_register_blocks(self, 
                                 block_size: int = 100,
                                 gap_threshold: int = 50) -> List[SlaveRegisterBlock]:
        """Generate optimized register blocks from parsed definitions
        
        Creates contiguous blocks of registers to minimize memory usage.
        Merges blocks that are close together (within gap_threshold).
        
        Args:
            block_size: Maximum size for auto-generated blocks
            gap_threshold: Maximum gap between registers to merge into same block
            
        Returns:
            List of SlaveRegisterBlock objects
        """
        if not self.registers:
            return []
        
        # Group registers by type
        by_type: Dict[str, List[RegisterDefinition]] = {
            "coils": [],
            "discrete": [],
            "input": [],
            "holding": []
        }
        
        for reg in self.registers:
            reg_type = self.POINT_TYPE_MAP.get(reg.point_type)
            if reg_type:
                by_type[reg_type].append(reg)
        
        # Generate blocks for each type
        blocks = []
        for reg_type, regs in by_type.items():
            if not regs:
                continue
            
            # Sort by index
            regs.sort(key=lambda r: r.index)
            
            # Create blocks with gap detection
            current_block_start = regs[0].index
            current_block_end = regs[0].index
            
            for i, reg in enumerate(regs[1:], start=1):
                gap = reg.index - current_block_end
                
                # If gap is too large or block is too large, finalize current block
                if gap > gap_threshold or (current_block_end - current_block_start + 1) >= block_size:
                    # Create block for current range
                    count = current_block_end - current_block_start + 1
                    block_name = f"{reg_type.upper()}_{current_block_start}-{current_block_end}"
                    
                    blocks.append(SlaveRegisterBlock(
                        name=block_name,
                        register_type=reg_type,
                        start_address=current_block_start,
                        count=count,
                        description=f"Auto-generated block: {count} registers"
                    ))
                    
                    # Start new block
                    current_block_start = reg.index
                    current_block_end = reg.index
                else:
                    # Extend current block
                    current_block_end = reg.index
            
            # Finalize last block
            if current_block_start <= current_block_end:
                count = current_block_end - current_block_start + 1
                block_name = f"{reg_type.upper()}_{current_block_start}-{current_block_end}"
                
                blocks.append(SlaveRegisterBlock(
                    name=block_name,
                    register_type=reg_type,
                    start_address=current_block_start,
                    count=count,
                    description=f"Auto-generated block: {count} registers"
                ))
        
        logger.info(f"Generated {len(blocks)} register blocks")
        return blocks
    
    def generate_signal_mappings(self) -> List[ModbusSignalMapping]:
        """Generate ModbusSignalMapping objects for all registers
        
        Only creates mappings for holding registers (read/write)
        
        Returns:
            List of ModbusSignalMapping objects
        """
        mappings = []
        
        for reg in self.registers:
            # Only create mappings for holding registers (writable)
            if reg.point_type != 4:  # Not holding register
                continue
            
            # Create mapping
            mapping = ModbusSignalMapping(
                address=reg.index,
                name=reg.name,
                description=reg.description,
                data_type=reg.data_type,
                endianness=reg.endianness,
                scale=reg.scale,
                offset=reg.offset,
                writable=True
            )
            mappings.append(mapping)
        
        logger.info(f"Generated {len(mappings)} signal mappings")
        return mappings
    
    def get_register_info(self, index: int) -> Optional[RegisterDefinition]:
        """Get register definition by index"""
        for reg in self.registers:
            if reg.index == index:
                return reg
        return None
    
    def get_registers_by_type(self, point_type: int) -> List[RegisterDefinition]:
        """Get all registers of a specific type"""
        return [r for r in self.registers if r.point_type == point_type]
    
    def export_summary(self) -> Dict[str, any]:
        """Export a summary of loaded registers"""
        by_type = {
            "coils": 0,
            "discrete": 0,
            "input": 0,
            "holding": 0
        }
        
        for reg in self.registers:
            reg_type = self.POINT_TYPE_MAP.get(reg.point_type)
            if reg_type:
                by_type[reg_type] += 1
        
        return {
            "total_registers": len(self.registers),
            "by_type": by_type,
            "index_range": {
                "min": min(r.index for r in self.registers) if self.registers else 0,
                "max": max(r.index for r in self.registers) if self.registers else 0
            }
        }


def import_csv_to_device_config(csv_path: str,
                                block_size: int = 100,
                                gap_threshold: int = 50) -> Tuple[List[SlaveRegisterBlock], List[ModbusSignalMapping]]:
    """Convenience function to import CSV and generate device configuration
    
    Args:
        csv_path: Path to CSV file
        block_size: Maximum size for auto-generated blocks
        gap_threshold: Maximum gap between registers to merge
        
    Returns:
        Tuple of (register_blocks, signal_mappings)
    """
    importer = CSVRegisterImporter()
    
    if not importer.parse_csv(csv_path):
        return ([], [])
    
    blocks = importer.generate_register_blocks(block_size, gap_threshold)
    mappings = importer.generate_signal_mappings()
    
    return (blocks, mappings)
