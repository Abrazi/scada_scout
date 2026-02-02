"""Test PLC runtime to diagnose variable update issues."""
import sys
import time
from src.models.plc_models import (
    PLCDeviceExtension, PLCProgram, PLCTask, PLCMode, TaskType,
    VariableScope, PLCVariable, PLCDataType, VariableQuality, IEC61131Language
)
from src.core.plc_runtime import PLCRuntime

def simple_log(level, msg):
    print(f"[{level.upper()}] {msg}")

# Create PLC device extension
plc_ext = PLCDeviceExtension()

# Create a simple program
program = PLCProgram(
    program_id="test_prog",
    name="TestCounter",
    language=IEC61131Language.STRUCTURED_TEXT,
    source_code="""PROGRAM TestCounter
VAR
    counter : INT := 0;
    running : BOOL := TRUE;
END_VAR

IF running THEN
    counter := counter + 1;
END_IF

END_PROGRAM
""",
    enabled=True
)

# Add variable
counter_var = PLCVariable(
    name="counter",
    data_type=PLCDataType.INT,
    initial_value=0,
    current_value=0,
    quality=VariableQuality.GOOD
)
running_var = PLCVariable(
    name="running",
    data_type=PLCDataType.BOOL,
    initial_value=True,
    current_value=True,
    quality=VariableQuality.GOOD
)
program.local_variables.variables.extend([counter_var, running_var])

# Compile program
from src.core.st_compiler import STCompiler
compiler = STCompiler()
result = compiler.compile(program)

if not result.success:
    print("❌ Compilation failed!")
    for err in result.errors:
        print(f"  Line {err.line}: {err.message}")
    sys.exit(1)

print("✓ Compilation successful")
program.compiled_code = result.bytecode

# Add program to PLC
plc_ext.programs.append(program)

# Create a task
task = PLCTask(
    task_id="main_task",
    name="MainTask",
    task_type=TaskType.CYCLIC,
    priority=1,
    interval_ms=100,
    enabled=True,
    program_ids=[program.program_id]  # CRITICAL: Assign program to task
)
plc_ext.tasks.append(task)

print(f"\nInitial state:")
print(f"  Programs: {len(plc_ext.programs)}")
print(f"  Tasks: {len(plc_ext.tasks)}")
print(f"  Task program_ids: {task.program_ids}")
print(f"  Program enabled: {program.enabled}")
print(f"  Program has bytecode: {program.compiled_code is not None}")
print(f"  counter.current_value: {counter_var.current_value}")
print(f"  running.current_value: {running_var.current_value}")

# Create runtime
runtime = PLCRuntime(plc_ext, simple_log)

# Start PLC in RUN mode
print("\n🚀 Starting PLC in RUN mode...")
if runtime.start():
    print("✓ PLC started")
else:
    print("❌ Failed to start PLC")
    sys.exit(1)

print(f"Operating mode: {plc_ext.operating_mode}")

# Wait and check variable updates
print("\n⏱️  Waiting 2 seconds for execution...")
time.sleep(2)

print(f"\nAfter 2 seconds:")
print(f"  Operating mode: {plc_ext.operating_mode}")
print(f"  Scan time: {plc_ext.scan_time_ms:.1f}ms")
print(f"  Uptime: {plc_ext.uptime_seconds:.1f}s")
print(f"  counter.current_value: {counter_var.current_value}")
print(f"  running.current_value: {running_var.current_value}")

# Check if counter increased
if isinstance(counter_var.current_value, int) and counter_var.current_value > 0:
    print(f"\n✅ SUCCESS! Counter incremented to {counter_var.current_value}")
else:
    print(f"\n❌ FAILURE! Counter did not increment (value: {counter_var.current_value})")

# Stop PLC
runtime.stop()
print("\n🛑 PLC stopped")
