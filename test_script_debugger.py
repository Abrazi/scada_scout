"""
Test script debugger functionality
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.script_debugger import ScriptDebugger, BreakpointInfo
import time


def test_breakpoint_management():
    """Test adding/removing breakpoints."""
    print("Testing breakpoint management...")
    
    debugger = ScriptDebugger()
    
    # Add breakpoint
    bp_id = debugger.add_breakpoint('<script>', 10)
    assert bp_id in debugger.breakpoints
    assert debugger.has_breakpoint_at_line('<script>', 10)
    
    # Remove breakpoint
    assert debugger.remove_breakpoint(bp_id)
    assert bp_id not in debugger.breakpoints
    assert not debugger.has_breakpoint_at_line('<script>', 10)
    
    print("✓ Breakpoint management works")


def test_simple_execution():
    """Test running simple code under debugger."""
    print("\nTesting simple code execution...")
    
    debugger = ScriptDebugger()
    results = []
    
    # Callback to track breaks
    def on_break(filename, line, locals_dict):
        results.append((line, locals_dict))
        # Auto-continue after break
        debugger.do_continue()
    
    def on_finish(exc):
        results.append(('finished', exc))
    
    debugger.on_break = on_break
    debugger.on_finish = on_finish
    
    # Add breakpoint at line 3
    debugger.add_breakpoint('<script>', 3)
    
    # Simple script
    code = """x = 10
y = 20
z = x + y  # breakpoint here
print(z)"""
    
    # Run in thread to avoid blocking
    from src.core.script_debugger import DebuggerThread
    thread = DebuggerThread(debugger, code, {}, '<script>')
    thread.start()
    thread.join(timeout=2)
    
    # Check results
    assert len(results) > 0
    print(f"✓ Debugger stopped at line {results[0][0]}")
    print(f"  Variables: {list(results[0][1].keys())}")


def test_step_operations():
    """Test stepping through code."""
    print("\nTesting step operations...")
    
    debugger = ScriptDebugger()
    steps = []
    
    def on_break(filename, line, locals_dict):
        steps.append(line)
        if len(steps) < 3:
            debugger.do_step_over()  # Step through first 3 lines
        else:
            debugger.do_continue()  # Then continue
    
    def on_finish(exc):
        steps.append('done')
    
    debugger.on_break = on_break
    debugger.on_finish = on_finish
    
    # Add breakpoint at first line
    debugger.add_breakpoint('<script>', 1)
    
    code = """a = 1
b = 2
c = 3
d = 4
print(a + b + c + d)"""
    
    from src.core.script_debugger import DebuggerThread
    thread = DebuggerThread(debugger, code, {}, '<script>')
    thread.start()
    thread.join(timeout=2)
    
    print(f"✓ Stepped through lines: {steps}")


def test_variable_inspection():
    """Test inspecting variables during debugging."""
    print("\nTesting variable inspection...")
    
    debugger = ScriptDebugger()
    captured_vars = {}
    
    def on_break(filename, line, locals_dict):
        captured_vars.update(locals_dict)
        debugger.do_continue()
    
    debugger.on_break = on_break
    debugger.add_breakpoint('<script>', 3)
    
    code = """x = 100
y = 200
z = x * y
print(z)"""
    
    from src.core.script_debugger import DebuggerThread
    thread = DebuggerThread(debugger, code, {}, '<script>')
    thread.start()
    thread.join(timeout=2)
    
    # Check we captured variables
    assert 'x' in captured_vars
    assert 'y' in captured_vars
    print(f"✓ Captured variables: {list(captured_vars.keys())}")
    print(f"  x = {captured_vars['x']}, y = {captured_vars['y']}")


if __name__ == '__main__':
    print("=" * 60)
    print("SCADA Scout Script Debugger Tests")
    print("=" * 60)
    
    try:
        test_breakpoint_management()
        test_simple_execution()
        test_step_operations()
        test_variable_inspection()
        
        print("\n" + "=" * 60)
        print("✓ All debugger tests passed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
