#!/usr/bin/env python3
"""Test PLC IDE Phase 1 implementation."""
import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.models.plc_models import (
    PLCDeviceExtension, PLCProgram, PLCTask, PLCMode,
    IEC61131Language, TaskType, PLCVariable, PLCDataType
)
from src.core.st_compiler import STCompiler
from src.core.plc_runtime import PLCRuntime
import time


def test_basic_program():
    """Test basic PLC program compilation and execution."""
    print("=" * 60)
    print("PLC IDE Phase 1 Test")
    print("=" * 60)
    
    # Create PLC extension
    plc = PLCDeviceExtension()
    plc.plc_type = "Simulated Test PLC"
    
    # Create a simple counter program
    program = PLCProgram(
        program_id="test_counter",
        name="SimpleCounter",
        language=IEC61131Language.STRUCTURED_TEXT,
        source_code="""PROGRAM SimpleCounter
VAR
    counter : INT := 0;
    running : BOOL := TRUE;
END_VAR

(* Increment counter *)
counter := counter + 1;

END_PROGRAM
"""
    )
    
    plc.add_program(program)
    
    # Create task
    task = PLCTask(
        task_id="main_task",
        name="MainTask",
        task_type=TaskType.CYCLIC,
        priority=10,
        interval_ms=100.0,
        program_ids=["test_counter"]
    )
    plc.add_task(task)
    
    # Compile
    print("\n1. Compiling program...")
    compiler = STCompiler()
    result = compiler.compile(program)
    
    if result.success:
        print("   ✓ Compilation successful")
        print(f"   - Input variables: {len(program.input_variables.variables)}")
        print(f"   - Local variables: {len(program.local_variables.variables)}")
    else:
        print("   ✗ Compilation failed:")
        for error in result.errors:
            print(f"     Line {error.line}: {error.message}")
        return False
    
    # Create runtime
    print("\n2. Creating PLC runtime...")
    runtime = PLCRuntime(plc)
    print(f"   ✓ Runtime created for {plc.plc_type}")
    
    # Start PLC
    print("\n3. Starting PLC (RUN mode)...")
    if runtime.start():
        print(f"   ✓ PLC started - Mode: {plc.operating_mode.value}")
    else:
        print("   ✗ Failed to start PLC")
        return False
    
    # Run for a few cycles
    print("\n4. Executing program (5 cycles)...")
    for i in range(5):
        time.sleep(0.15)  # Let scan cycle execute
        counter_var = program.local_variables.get_variable("counter")
        if counter_var:
            print(f"   Cycle {i+1}: counter = {counter_var.current_value}, scan_time = {plc.scan_time_ms:.2f}ms")
        else:
            print(f"   Cycle {i+1}: Variable not found")
    
    # Stop PLC
    print("\n5. Stopping PLC...")
    if runtime.stop():
        print(f"   ✓ PLC stopped - Mode: {plc.operating_mode.value}")
    else:
        print("   ✗ Failed to stop PLC")
    
    print("\n" + "=" * 60)
    print("✓ Test completed successfully!")
    print("=" * 60)
    
    return True


def test_temperature_controller():
    """Test more complex temperature control program."""
    print("\n" + "=" * 60)
    print("Temperature Controller Test")
    print("=" * 60)
    
    plc = PLCDeviceExtension()
    
    program = PLCProgram(
        program_id="temp_ctrl",
        name="TempController",
        language=IEC61131Language.STRUCTURED_TEXT,
        source_code="""PROGRAM TempController
VAR_INPUT
    sensorTemp : REAL := 25.0;
    setpoint : REAL := 50.0;
END_VAR
VAR_OUTPUT
    heaterOn : BOOL := FALSE;
END_VAR
VAR
    hysteresis : REAL := 2.0;
END_VAR

(* Bang-bang temperature control *)
IF sensorTemp < (setpoint - hysteresis) THEN
    heaterOn := TRUE
ELSIF sensorTemp > (setpoint + hysteresis) THEN
    heaterOn := FALSE
END_IF

END_PROGRAM
"""
    )
    
    plc.add_program(program)
    
    # Compile
    print("\n1. Compiling temperature controller...")
    compiler = STCompiler()
    result = compiler.compile(program)
    
    if result.success:
        print("   ✓ Compilation successful")
        print(f"   - Input variables: {[v.name for v in program.input_variables.variables]}")
        print(f"   - Output variables: {[v.name for v in program.output_variables.variables]}")
        print(f"   - Local variables: {[v.name for v in program.local_variables.variables]}")
    else:
        print("   ✗ Compilation failed")
        for error in result.errors:
            print(f"     Line {error.line}: {error.message}")
        return False
    
    # Create task
    task = PLCTask(
        task_id="ctrl_task",
        name="ControlTask",
        task_type=TaskType.CYCLIC,
        interval_ms=50.0,
        program_ids=["temp_ctrl"]
    )
    plc.add_task(task)
    
    # Create runtime and start
    print("\n2. Starting PLC runtime...")
    runtime = PLCRuntime(plc)
    runtime.start()
    
    # Simulate temperature rising
    print("\n3. Simulating temperature changes...")
    sensor_var = program.input_variables.get_variable("sensorTemp")
    heater_var = program.output_variables.get_variable("heaterOn")
    
    for temp in [25, 30, 40, 48, 52, 55]:
        if sensor_var:
            sensor_var.current_value = float(temp)
        time.sleep(0.1)
        
        heater_status = heater_var.current_value if heater_var else None
        print(f"   Temp: {temp}°C -> Heater: {'ON' if heater_status else 'OFF'}")
    
    runtime.stop()
    
    print("\n✓ Temperature controller test completed!")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    try:
        success = test_basic_program()
        if success:
            test_temperature_controller()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
