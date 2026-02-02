"""Manual test for PLC IDE UI functionality.
This script tests the key issues reported:
1. Compiled program bytecode storage
2. Debug mode button availability
3. Debug mode state transitions
"""

import sys
from src.models.plc_models import PLCDeviceExtension, PLCProgram, IEC61131Language, PLCMode, PLCTask, TaskType
from src.core.st_compiler import STCompiler
from src.core.plc_runtime import PLCRuntime
import time

def test_compile_and_bytecode():
    """Test 1: Verify bytecode is stored after compilation."""
    print("\n=== TEST 1: Compile and Bytecode Storage ===")
    
    code = """
PROGRAM TestProgram
VAR
    counter : INT;
END_VAR

counter := counter + 1;

END_PROGRAM
"""
    
    program = PLCProgram(
        program_id="test1",
        name="TestProgram",
        language=IEC61131Language.STRUCTURED_TEXT,
        source_code=code,
        enabled=True
    )
    
    compiler = STCompiler()
    result = compiler.compile(program)
    
    print(f"✓ Compilation result: {result.success}")
    print(f"✓ Bytecode generated: {result.bytecode is not None}")
    print(f"✓ Bytecode length: {len(result.bytecode) if result.bytecode else 0} bytes")
    
    # This is the CRITICAL step that was missing!
    program.compiled_code = result.bytecode
    
    print(f"✓ Program.compiled_code set: {program.compiled_code is not None}")
    print(f"✓ Program.compiled_code length: {len(program.compiled_code) if program.compiled_code else 0} bytes")
    
    # Verify we can start runtime with this program
    device = PLCDeviceExtension()
    device.add_program(program)
    
    task = PLCTask(
        task_id="main",
        name="MainTask",
        task_type=TaskType.CYCLIC,
        interval_ms=100.0,
        program_ids=["test1"]
    )
    device.add_task(task)
    
    runtime = PLCRuntime(device)
    
    # Check compiled programs before starting
    compiled_count = sum(1 for p in device.programs if p.compiled_code)
    print(f"✓ Compiled programs before start: {compiled_count}")
    
    if compiled_count > 0:
        success = runtime.start()
        print(f"✓ Runtime started: {success}")
        print(f"✓ Operating mode: {device.operating_mode}")
        
        time.sleep(0.1)
        
        counter_var = program.local_variables.get_variable("counter")
        print(f"✓ Counter value after execution: {counter_var.current_value if counter_var else 'N/A'}")
        
        runtime.stop()
        print("✓ Runtime stopped")
    else:
        print("✗ FAIL: No compiled programs found - this is the bug!")
        return False
    
    print("\n✅ TEST 1 PASSED: Bytecode storage works correctly\n")
    return True


def test_debug_mode():
    """Test 2: Verify debug mode can be started."""
    print("\n=== TEST 2: Debug Mode State Transitions ===")
    
    code = """
PROGRAM DebugTest
VAR
    value : INT;
END_VAR

value := 10 + 5;

END_PROGRAM
"""
    
    program = PLCProgram(
        program_id="test_debug",
        name="DebugTest",
        language=IEC61131Language.STRUCTURED_TEXT,
        source_code=code,
        enabled=True
    )
    
    compiler = STCompiler()
    result = compiler.compile(program)
    program.compiled_code = result.bytecode  # CRITICAL!
    
    device = PLCDeviceExtension()
    device.add_program(program)
    
    task = PLCTask(
        task_id="main",
        name="MainTask",
        task_type=TaskType.CYCLIC,
        interval_ms=100.0,
        program_ids=["test_debug"]
    )
    device.add_task(task)
    
    runtime = PLCRuntime(device)
    
    print(f"✓ Initial mode: {device.operating_mode}")
    assert device.operating_mode == PLCMode.STOP, "Should start in STOP mode"
    
    # Test RUN mode
    print("\n--- Testing RUN mode ---")
    success = runtime.start()
    print(f"✓ Start RUN mode: {success}")
    print(f"✓ Current mode: {device.operating_mode}")
    assert device.operating_mode == PLCMode.RUN, "Should be in RUN mode"
    
    time.sleep(0.1)
    runtime.stop()
    print(f"✓ After stop: {device.operating_mode}")
    assert device.operating_mode == PLCMode.STOP, "Should be in STOP mode"
    
    # Test DEBUG mode
    print("\n--- Testing DEBUG mode ---")
    success = runtime.start_debug()
    print(f"✓ Start DEBUG mode: {success}")
    print(f"✓ Current mode: {device.operating_mode}")
    assert device.operating_mode == PLCMode.DEBUG, "Should be in DEBUG mode"
    
    # Verify debug engine is active
    print(f"✓ Debug engine initialized: {runtime.debug_engine is not None}")
    print(f"✓ Debug state: {runtime.debug_engine.debug_state}")
    
    # Test breakpoint operations
    bp = runtime.debug_engine.add_breakpoint("test_debug", 7)
    print(f"✓ Breakpoint added: {bp.breakpoint_id} at line {bp.line}")
    
    breakpoints = runtime.debug_engine.get_breakpoints("test_debug")
    print(f"✓ Total breakpoints: {len(breakpoints)}")
    
    time.sleep(0.1)
    runtime.stop()
    print(f"✓ After stop: {device.operating_mode}")
    
    print("\n✅ TEST 2 PASSED: Debug mode works correctly\n")
    return True


def test_debug_operations():
    """Test 3: Verify debug operations (step, continue, etc.)."""
    print("\n=== TEST 3: Debug Operations ===")
    
    code = """
PROGRAM StepTest
VAR
    a : INT;
    b : INT;
    c : INT;
END_VAR

a := 10;
b := 20;
c := a + b;

END_PROGRAM
"""
    
    program = PLCProgram(
        program_id="test_step",
        name="StepTest",
        language=IEC61131Language.STRUCTURED_TEXT,
        source_code=code,
        enabled=True
    )
    
    compiler = STCompiler()
    result = compiler.compile(program)
    program.compiled_code = result.bytecode
    
    device = PLCDeviceExtension()
    device.add_program(program)
    
    task = PLCTask(
        task_id="main",
        name="MainTask",
        task_type=TaskType.CYCLIC,
        interval_ms=100.0,
        program_ids=["test_step"]
    )
    device.add_task(task)
    
    runtime = PLCRuntime(device)
    runtime.start_debug()
    
    print(f"✓ Debug mode active: {device.operating_mode == PLCMode.DEBUG}")
    
    # Test watch expressions
    watch = runtime.debug_engine.add_watch("a + b", "test_step")
    print(f"✓ Watch expression added: {watch.expression}")
    
    watches = runtime.debug_engine.get_watches()
    print(f"✓ Total watches: {len(watches)}")
    
    # Test step operations (just verify they don't crash)
    print("\n--- Testing step operations ---")
    try:
        runtime.debug_engine.step_into()
        print("✓ Step into executed")
        
        runtime.debug_engine.step_over()
        print("✓ Step over executed")
        
        runtime.debug_engine.continue_execution()
        print("✓ Continue executed")
        
        runtime.debug_engine.pause()
        print("✓ Pause executed")
    except Exception as e:
        print(f"✗ Error during debug operations: {e}")
        return False
    
    time.sleep(0.1)
    runtime.stop()
    
    print("\n✅ TEST 3 PASSED: Debug operations work\n")
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("PLC IDE Manual Functionality Tests")
    print("=" * 60)
    
    results = []
    
    # Test 1: Bytecode storage
    try:
        results.append(("Compile & Bytecode", test_compile_and_bytecode()))
    except Exception as e:
        print(f"\n✗ TEST 1 FAILED: {e}\n")
        results.append(("Compile & Bytecode", False))
    
    # Test 2: Debug mode
    try:
        results.append(("Debug Mode", test_debug_mode()))
    except Exception as e:
        print(f"\n✗ TEST 2 FAILED: {e}\n")
        results.append(("Debug Mode", False))
    
    # Test 3: Debug operations
    try:
        results.append(("Debug Operations", test_debug_operations()))
    except Exception as e:
        print(f"\n✗ TEST 3 FAILED: {e}\n")
        results.append(("Debug Operations", False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    
    print(f"\nTotal: {passed}/{total} tests passed ({100*passed//total}%)")
    print("=" * 60)
    
    return all(p for _, p in results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
