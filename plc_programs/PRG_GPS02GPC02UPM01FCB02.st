(* ========================================================================
   PLC PROGRAM: PRG_GPS02GPC02UPM01FCB02
   IED: GPS02GPC02UPM01FCB02
   Device: GPS02GPC02UPM01FCB02
   Generated: 2026-02-05 10:23:38
   
   This program runs cyclically (default 100ms) and has access to all
   data points of the associated IEC 61850 device. Users can add custom
   logic in the designated sections below.
   ======================================================================== *)

PROGRAM PRG_GPS02GPC02UPM01FCB02
VAR
    (* ====== System Variables ====== *)
    cycle_count: UDINT := 0;           (* Increments each scan cycle *)
    first_scan: BOOL := TRUE;          (* TRUE only on first execution *)
    scan_time_ms: REAL := 0.0;         (* Last scan time in milliseconds *)
    
    (* ====== IED Connection Status ====== *)
    ied_connected: BOOL := FALSE;      (* TRUE when IED server is running *)
    ied_name: STRING := 'GPS02GPC02UPM01FCB02';
    device_name: STRING := 'GPS02GPC02UPM01FCB02';
    
    (* ====== Logical Devices ====== *)
    (* Available LDs: AnUn_ArcProtInput1, Application, BinIO, BinIO_BinaryInputs, BinIO_BinaryOutputs, CB1, CB1_Fundamental, Ds1, Ds2, Mod1, Mod1_Channel1, Mod2, Mod2_Channel1, Mod3, Mod3_Channel1, PowS, PowS_MeasPointI3ph1, PowS_MeasPointV3ph1, Rec, Rec_FaultRecorder, VI3p1, VI3p1_5051NOCgndB1, VI3p1_5051OC3phase1, VI3p1_ArcProtection1, VI3p1_Energy, VI3p1_FundSymComp, VI3p1_OperationalValues, VI3p1_ProcessMonitor, VI3p1_ExternalTrip1, VI3p1_67DirOC3phB1, VI3p1_67NDirOCgndB1, ComSupervision, ComSupervision_GOOSE *)
    
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
