"""Simple test to verify execution is working."""
import time
from src.models.plc_models import (
    PLCDeviceExtension, PLCProgram, IEC61131Language, 
    PLCTask, TaskType
)
from src.core.st_compiler import STCompiler
from src.core.plc_runtime import PLCRuntime
import logging

logging.basicConfig(level=logging.DEBUG)

code = """
PROGRAM Test
VAR
    counter : INT;
END_VAR

counter := counter + 1;

END_PROGRAM
"""

program = PLCProgram(
    program_id="test",
    name="Test",
    language=IEC61131Language.STRUCTURED_TEXT,
    source_code=code,
    enabled=True
)

compiler = STCompiler()
result = compiler.compile(program)
print(f"Compile success: {result.success}")
print(f"Bytecode: {result.bytecode}")

program.compiled_code = result.bytecode

device = PLCDeviceExtension()
device.add_program(program)

task = PLCTask(
    task_id="main",
    name="MainTask",
    task_type=TaskType.CYCLIC,
    interval_ms=100.0,
    program_ids=["test"]
)
device.add_task(task)

print(f"Device programs: {len(device.programs)}")
print(f"Device tasks: {len(device.tasks)}")
print(f"Program enabled: {program.enabled}")
print(f"Program has compiled_code: {program.compiled_code is not None}")
print(f"Task program_ids: {task.program_ids}")

runtime = PLCRuntime(device)

print("Starting runtime...")
runtime.start()

print("Waiting...")
time.sleep(0.5)

print(f"Operating mode: {device.operating_mode}")
print(f"Runtime running: {runtime._running}")

counter_var = program.local_variables.get_variable("counter")
print(f"Counter value: {counter_var.current_value}")

runtime.stop()
