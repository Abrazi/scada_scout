"""Simple test to diagnose PLC runtime issues."""
import sys
import time
import logging

# Enable DEBUG logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

# Add correct path
sys.path.insert(0, '/home/majid/Documents/scada_scout')

from src.models.plc_models import (
    PLCDeviceExtension, PLCProgram, PLCTask, PLCMode, TaskType,
    VariableScope, PLCVariable, PLCDataType, VariableQuality, IEC61131Language
)
from src.core.plc_runtime import PLCRuntime
from src.core.st_compiler import STCompiler

def simple_log(level, msg):
    print(f"[{level}] {msg}")

# Create PLC device
plc_ext = PLCDeviceExtension()

# Create program
program = PLCProgram(
    program_id="test1",
    name="Counter",
    language=IEC61131Language.STRUCTURED_TEXT,
    source_code="""PROGRAM Counter
VAR
    count : INT := 0;
END_VAR

count := count + 1;

END_PROGRAM
"""
)

# Add variable
count_var = PLCVariable(
    name="count",
    data_type=PLCDataType.INT,
    initial_value=0
)
program.local_variables.variables.append(count_var)
program.enabled = True

# Compile
compiler = STCompiler()
result = compiler.compile(program)

if not result.success:
    print("COMPILATION FAILED!")
    for err in result.errors:
        print(f"  Error: {err.message}")
    sys.exit(1)

print("✓ Compilation successful")
program.compiled_code = result.bytecode

# Add to PLC
plc_ext.programs.append(program)

# Create task with program assigned
task = PLCTask(
    task_id="main",
    name="MainTask",
    task_type=TaskType.CYCLIC,
    priority=1,
    interval_ms=100,
    enabled=True,
    program_ids=[program.program_id]  # ASSIGN PROGRAM TO TASK!
)
plc_ext.tasks.append(task)

print(f"\n=== Initial State ===")
print(f"Programs: {len(plc_ext.programs)}")
print(f"Tasks: {len(plc_ext.tasks)}")
print(f"Task program_ids: {task.program_ids}")
print(f"Program has bytecode: {program.compiled_code is not None}")
print(f"count.current_value: {count_var.current_value}")

# Create runtime and start
runtime = PLCRuntime(plc_ext, simple_log)

print(f"\n=== Starting PLC ===")
if runtime.start():
    print("✓ PLC started")
else:
    print("✗ Failed to start")
    sys.exit(1)

print(f"Mode: {plc_ext.operating_mode}")

# Wait for execution
print(f"\nWaiting 2 seconds...")
time.sleep(2)

print(f"\n=== After 2 Seconds ===")
print(f"Mode: {plc_ext.operating_mode}")
print(f"Scan time: {plc_ext.scan_time_ms:.2f}ms")
print(f"Uptime: {plc_ext.uptime_seconds:.2f}s")

# Get variable from program (not original reference)
count_var_from_program = program.local_variables.get_variable('count')
print(f"count_var_from_program.current_value: {count_var_from_program.current_value if count_var_from_program else 'NOT FOUND'}")
print(f"count_var (original ref).current_value: {count_var.current_value}")

if count_var_from_program and isinstance(count_var_from_program.current_value, int) and count_var_from_program.current_value > 0:
    print(f"\n✅ SUCCESS! Counter = {count_var_from_program.current_value}")
else:
    print(f"\n❌ FAILED! Counter = {count_var_from_program.current_value if count_var_from_program else 'NOT FOUND'}")

runtime.stop()
