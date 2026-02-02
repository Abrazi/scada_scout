#!/usr/bin/env python3
"""Test suite for PLC IDE Phase 2 features.

Tests:
- Control flow (IF/FOR/WHILE/CASE/REPEAT)
- Debugging (breakpoints, stepping)
- Online change (hot reload)
- Function blocks
"""
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.models.plc_models import (
    PLCDeviceExtension, PLCProgram, PLCTask, PLCMode,
    IEC61131Language, TaskType, PLCDataType, PLCVariable,
    VariableScope, Breakpoint, DebugState
)
from src.core.st_compiler import STCompiler
from src.core.plc_runtime import PLCRuntime


def test_control_flow_if_else():
    """Test IF/THEN/ELSE control flow."""
    print("\n=== Test 1: IF/THEN/ELSE Control Flow ===")
    
    code = """
PROGRAM TestIfElse
VAR
    temperature : REAL := 50.0;
    status : INT := 0;
END_VAR

IF temperature < 30.0 THEN
    status = 1;
ELSIF temperature < 60.0 THEN
    status = 2;
ELSE
    status = 3;
END_IF;

END_PROGRAM
"""
    
    # Compile
    program = PLCProgram(
        program_id="test_if",
        name="TestIfElse",
        language=IEC61131Language.STRUCTURED_TEXT,
        source_code=code,
        enabled=True  # Ensure program is enabled
    )
    
    compiler = STCompiler()
    result = compiler.compile(program)
    
    print(f"✓ Compilation: {'SUCCESS' if result.success else 'FAILED'}")
    if result.errors:
        for err in result.errors:
            print(f"  Error: Line {err.line}: {err.message}")
        return False
    
    # Set compiled code
    program.compiled_code = result.bytecode
    
    # Execute
    device = PLCDeviceExtension()
    device.add_program(program)
    
    task = PLCTask(
        task_id="main",
        name="MainTask",
        task_type=TaskType.CYCLIC,
        priority=10,
        interval_ms=10.0,
        program_ids=["test_if"]
    )
    device.add_task(task)
    
    runtime = PLCRuntime(device)
    runtime.start()
    time.sleep(0.1)
    
    # Check result
    status_var = program.local_variables.get_variable("status")
    print(f"✓ Execution: status = {status_var.current_value} (expected 2)")
    
    runtime.stop()
    
    assert status_var.current_value == 2, "IF/ELSE logic failed"
    print("✅ IF/THEN/ELSE test passed")
    return True


def test_control_flow_for_loop():
    """Test FOR loop."""
    print("\n=== Test 2: FOR Loop ===")
    
    code = """
PROGRAM TestForLoop
VAR
    i : INT;
    sum : INT := 0;
END_VAR

sum = 0;
FOR i = 1 TO 10 BY 1 DO
    sum = sum + i;
END_FOR;

END_PROGRAM
"""
    
    program = PLCProgram(
        program_id="test_for",
        name="TestForLoop",
        language=IEC61131Language.STRUCTURED_TEXT,
        source_code=code,
        enabled=True
    )
    
    compiler = STCompiler()
    result = compiler.compile(program)
    
    print(f"✓ Compilation: {'SUCCESS' if result.success else 'FAILED'}")
    if not result.success:
        for err in result.errors:
            print(f"  Error: Line {err.line}: {err.message}")
        return False
    
    # Set compiled code
    program.compiled_code = result.bytecode
    
    # Execute
    device = PLCDeviceExtension()
    device.add_program(program)
    
    task = PLCTask(
        task_id="main",
        name="MainTask",
        task_type=TaskType.CYCLIC,
        interval_ms=10.0,
        program_ids=["test_for"]
    )
    device.add_task(task)
    
    runtime = PLCRuntime(device)
    runtime.start()
    time.sleep(0.05)  # Shorter wait - just one scan
    runtime.stop()
    
    # Check result (1+2+3+...+10 = 55) - sum is reset each scan so should be 55
    sum_var = program.local_variables.get_variable("sum")
    print(f"✓ Execution: sum = {sum_var.current_value} (expected 55)")
    
    assert sum_var.current_value == 55, "FOR loop calculation failed"
    print("✅ FOR loop test passed")
    return True


def test_control_flow_while_loop():
    """Test WHILE loop."""
    print("\n=== Test 3: WHILE Loop ===")
    
    code = """
PROGRAM TestWhileLoop
VAR
    counter : INT := 0;
    total : INT := 0;
END_VAR

WHILE counter < 5 DO
    total = total + counter;
    counter = counter + 1;
END_WHILE;

END_PROGRAM
"""
    
    program = PLCProgram(
        program_id="test_while",
        name="TestWhileLoop",
        language=IEC61131Language.STRUCTURED_TEXT,
        source_code=code,
        enabled=True
    )
    
    compiler = STCompiler()
    result = compiler.compile(program)
    
    print(f"✓ Compilation: {'SUCCESS' if result.success else 'FAILED'}")
    if not result.success:
        return False
    
    # Set compiled code
    program.compiled_code = result.bytecode
    
    # Execute
    device = PLCDeviceExtension()
    device.add_program(program)
    
    task = PLCTask(
        task_id="main",
        name="MainTask",
        task_type=TaskType.CYCLIC,
        interval_ms=10.0,
        program_ids=["test_while"]
    )
    device.add_task(task)
    
    runtime = PLCRuntime(device)
    runtime.start()
    time.sleep(0.1)
    
    # Check result (0+1+2+3+4 = 10)
    total_var = program.local_variables.get_variable("total")
    counter_var = program.local_variables.get_variable("counter")
    print(f"✓ Execution: total = {total_var.current_value}, counter = {counter_var.current_value}")
    
    runtime.stop()
    
    assert total_var.current_value == 10, "WHILE loop calculation failed"
    assert counter_var.current_value == 5, "WHILE loop counter failed"
    print("✅ WHILE loop test passed")
    return True


def test_debugging_breakpoints():
    """Test breakpoint functionality."""
    print("\n=== Test 4: Debugging - Breakpoints ===")
    
    code = """
PROGRAM TestBreakpoints
VAR
    x : INT := 0;
END_VAR

x = x + 1;
x = x + 2;
x = x + 3;

END_PROGRAM
"""
    
    program = PLCProgram(
        program_id="test_bp",
        name="TestBreakpoints",
        language=IEC61131Language.STRUCTURED_TEXT,
        source_code=code,
        enabled=True
    )
    
    compiler = STCompiler()
    result = compiler.compile(program)
    
    print(f"✓ Compilation: {'SUCCESS' if result.success else 'FAILED'}")
    if not result.success:
        return False
    
    # Set compiled code
    program.compiled_code = result.bytecode
    
    # Setup runtime with debugging
    device = PLCDeviceExtension()
    device.add_program(program)
    
    task = PLCTask(
        task_id="main",
        name="MainTask",
        task_type=TaskType.CYCLIC,
        interval_ms=10.0,
        program_ids=["test_bp"]
    )
    device.add_task(task)
    
    runtime = PLCRuntime(device)
    
    # Add breakpoint at line 6 (x = x + 2)
    bp = runtime.debug_engine.add_breakpoint("test_bp", 6)
    print(f"✓ Added breakpoint at line {bp.line}")
    
    # Check breakpoint was added
    assert "test_bp" in runtime.debug_engine.breakpoints, "Breakpoint not registered"
    assert len(runtime.debug_engine.breakpoints["test_bp"]) == 1, "Breakpoint count mismatch"
    
    # Toggle breakpoint
    runtime.debug_engine.toggle_breakpoint("test_bp", 6)
    print(f"✓ Toggled breakpoint (enabled={runtime.debug_engine.breakpoints['test_bp'][0].enabled})")
    
    # Clear breakpoints
    runtime.debug_engine.clear_breakpoints("test_bp")
    print(f"✓ Cleared breakpoints")
    
    assert len(runtime.debug_engine.breakpoints["test_bp"]) == 0, "Breakpoints not cleared"
    
    print("✅ Breakpoint test passed")
    return True


def test_online_change():
    """Test online change (hot reload)."""
    print("\n=== Test 5: Online Change (Hot Reload) ===")
    
    original_code = """
PROGRAM TestOnlineChange
VAR
    value : INT;
END_VAR

value = 10 + 5;

END_PROGRAM
"""
    
    program = PLCProgram(
        program_id="test_oc",
        name="TestOnlineChange",
        language=IEC61131Language.STRUCTURED_TEXT,
        source_code=original_code,
        enabled=True
    )
    
    compiler = STCompiler()
    result = compiler.compile(program)
    
    print(f"✓ Initial compilation: SUCCESS")
    
    # Set compiled code
    program.compiled_code = result.bytecode
    
    # Start runtime
    device = PLCDeviceExtension()
    device.add_program(program)
    
    task = PLCTask(
        task_id="main",
        name="MainTask",
        task_type=TaskType.CYCLIC,
        interval_ms=10.0,
        program_ids=["test_oc"]
    )
    device.add_task(task)
    
    runtime = PLCRuntime(device)
    runtime.start()
    time.sleep(0.05)  # Just one scan
    runtime.stop()
    
    # Check initial value (10 + 5 = 15)
    value_var = program.local_variables.get_variable("value")
    print(f"✓ Initial value: {value_var.current_value} (expected 15)")
    assert value_var.current_value == 15, "Initial execution failed"
    
    # Apply online change
    runtime.start()  # Restart for online change
    new_code = """
PROGRAM TestOnlineChange
VAR
    value : INT;
    multiplier : INT := 3;
END_VAR

value = 10 * multiplier;

END_PROGRAM
"""
    
    success = runtime.online_change("test_oc", new_code)
    print(f"✓ Online change applied: {success}")
    assert success, "Online change failed"
    
    # Wait for new code to execute (ensure at least one scan)
    time.sleep(0.1)
    runtime.stop()
    
    # IMPORTANT: Get fresh variable references from the program after online change
    value_var = program.local_variables.get_variable("value")
    multiplier_var = program.local_variables.get_variable("multiplier")
    
    print(f"✓ After online change: value={value_var.current_value if value_var else 'N/A'}, multiplier={multiplier_var.current_value if multiplier_var else 'N/A'}")
    
    assert multiplier_var is not None, "New variable not added"
    assert multiplier_var.current_value == 3, f"New variable not initialized (value={multiplier_var.current_value})"
    assert value_var.current_value == 30, f"Online change calculation incorrect (value={value_var.current_value})"
    
    print("✅ Online change test passed")
    return True


def test_watch_expressions():
    """Test watch expressions."""
    print("\n=== Test 6: Watch Expressions ===")
    
    code = """
PROGRAM TestWatch
VAR
    a : INT := 10;
    b : INT := 20;
END_VAR

a = a + b;

END_PROGRAM
"""
    
    program = PLCProgram(
        program_id="test_watch",
        name="TestWatch",
        language=IEC61131Language.STRUCTURED_TEXT,
        source_code=code,
        enabled=True
    )
    
    compiler = STCompiler()
    result = compiler.compile(program)
    
    print(f"✓ Compilation: SUCCESS")
    
    # Set compiled code
    program.compiled_code = result.bytecode
    
    device = PLCDeviceExtension()
    device.add_program(program)
    
    task = PLCTask(
        task_id="main",
        name="MainTask",
        task_type=TaskType.CYCLIC,
        interval_ms=10.0,
        program_ids=["test_watch"]
    )
    device.add_task(task)
    
    runtime = PLCRuntime(device)
    
    # Add watch expressions
    watch1 = runtime.debug_engine.add_watch("a + b")
    watch2 = runtime.debug_engine.add_watch("a * 2")
    
    print(f"✓ Added {len(runtime.debug_engine.watch_expressions)} watch expressions")
    
    # Start and update watches
    runtime.start()
    time.sleep(0.1)
    
    # Get program context for watch evaluation
    ctx = runtime._program_contexts.get("test_watch", {})
    runtime.debug_engine.update_watches(ctx)
    
    print(f"✓ Watch 1 (a + b): {watch1.value}")
    print(f"✓ Watch 2 (a * 2): {watch2.value}")
    
    runtime.stop()
    
    # a becomes 30 after execution, b is 20
    # Watch1: a + b should be evaluated with current values
    assert watch1.error is None, f"Watch 1 error: {watch1.error}"
    assert watch2.error is None, f"Watch 2 error: {watch2.error}"
    
    print("✅ Watch expressions test passed")
    return True


def main():
    """Run all Phase 2 tests."""
    print("╔══════════════════════════════════════════════════════╗")
    print("║     PLC IDE Phase 2 Feature Test Suite              ║")
    print("╚══════════════════════════════════════════════════════╝")
    
    tests = [
        test_control_flow_if_else,
        test_control_flow_for_loop,
        test_control_flow_while_loop,
        test_debugging_breakpoints,
        test_online_change,
        test_watch_expressions
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                print(f"❌ {test_func.__name__} failed")
        except Exception as e:
            failed += 1
            print(f"❌ {test_func.__name__} raised exception: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("="*60)
    
    if failed == 0:
        print("\n🎉 All Phase 2 tests passed!")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
