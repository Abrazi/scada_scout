"""
Python script debugger backend for SCADA Scout.
Provides breakpoint management, step-by-step execution, and variable inspection.
"""
import bdb
import sys
import threading
import traceback
from typing import Dict, List, Optional, Callable, Any, Set
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class BreakpointInfo:
    """Information about a breakpoint."""
    file: str
    line: int
    enabled: bool = True
    condition: Optional[str] = None
    hit_count: int = 0


@dataclass
class StackFrame:
    """Information about a stack frame."""
    file: str
    line: int
    function: str
    locals: Dict[str, Any]
    code_context: List[str]


class ScriptDebugger(bdb.Bdb):
    """
    Debugger for SCADA Scout Python scripts.
    Supports breakpoints, stepping, variable inspection.
    """
    
    def __init__(self):
        super().__init__()
        self.breakpoints: Dict[int, BreakpointInfo] = {}  # bp_id -> BreakpointInfo
        self._next_bp_id = 1
        self._line_breakpoints: Dict[str, Set[int]] = {}  # file -> set of line numbers
        
        # Debugger state
        self.is_running = False
        self.is_paused = False
        self._continue_event = threading.Event()
        self._step_mode = None  # None, 'over', 'into', 'out'
        self._step_frame = None
        
        # Callbacks
        self.on_break: Optional[Callable[[str, int, Dict[str, Any]], None]] = None
        self.on_step: Optional[Callable[[str, int], None]] = None
        self.on_finish: Optional[Callable[[Optional[Exception]], None]] = None
        self.on_output: Optional[Callable[[str], None]] = None
        
        # Execution state
        self._current_frame = None
        self._exception = None
        
        # User code tracking
        self._user_files: Set[str] = set()
        self._workspace_root: Optional[str] = None
    
    def _is_user_code(self, filename: str) -> bool:
        """Check if the file is user code (not system/library code)."""
        # Skip frozen/built-in modules
        if filename.startswith('<') or 'frozen' in filename:
            return False

        import os

        # Normalize path for comparison
        normalized_filename = os.path.abspath(os.path.normpath(filename))

        # If explicitly tracked, it's user code
        if self._user_files and normalized_filename in self._user_files:
            return True

        # If workspace root is known, only allow files under it
        if self._workspace_root:
            return normalized_filename.startswith(self._workspace_root + os.sep)

        # Fallback: treat as non-user code
        return False
        
    def add_breakpoint(self, file: str, line: int, condition: Optional[str] = None) -> int:
        """Add a breakpoint and return its ID."""
        import os
        
        bp_id = self._next_bp_id
        self._next_bp_id += 1
        
        bp = BreakpointInfo(file=file, line=line, condition=condition)
        self.breakpoints[bp_id] = bp
        
        # Track by file/line for quick lookup
        if file not in self._line_breakpoints:
            self._line_breakpoints[file] = set()
        self._line_breakpoints[file].add(line)
        
        # Track as user file (normalized)
        normalized_file = os.path.abspath(os.path.normpath(file))
        self._user_files.add(normalized_file)
        logger.info(f"Tracked user file: {normalized_file}")
        
        # Set bdb breakpoint
        self.set_break(file, line)
        
        logger.info(f"Breakpoint {bp_id} added at {file}:{line}")
        return bp_id
    
    def remove_breakpoint(self, bp_id: int) -> bool:
        """Remove a breakpoint by ID."""
        if bp_id not in self.breakpoints:
            return False
        
        bp = self.breakpoints[bp_id]
        
        # Remove from tracking
        if bp.file in self._line_breakpoints:
            self._line_breakpoints[bp.file].discard(bp.line)
            if not self._line_breakpoints[bp.file]:
                del self._line_breakpoints[bp.file]
        
        # Clear bdb breakpoint
        self.clear_break(bp.file, bp.line)
        
        del self.breakpoints[bp_id]
        logger.info(f"Breakpoint {bp_id} removed")
        return True
    
    def toggle_breakpoint(self, bp_id: int) -> bool:
        """Enable/disable a breakpoint."""
        if bp_id not in self.breakpoints:
            return False
        
        bp = self.breakpoints[bp_id]
        bp.enabled = not bp.enabled
        
        if bp.enabled:
            self.set_break(bp.file, bp.line)
        else:
            self.clear_break(bp.file, bp.line)
        
        return bp.enabled
    
    def clear_all_breakpoints(self):
        """Remove all breakpoints."""
        for bp_id in list(self.breakpoints.keys()):
            self.remove_breakpoint(bp_id)
    
    def has_breakpoint_at_line(self, file: str, line: int) -> bool:
        """Check if there's a breakpoint at the given line."""
        import os
        
        # Normalize the incoming file path
        normalized_file = os.path.abspath(os.path.normpath(file))
        
        # Check against all tracked breakpoint files
        for bp_file, lines in self._line_breakpoints.items():
            normalized_bp_file = os.path.abspath(os.path.normpath(bp_file))
            if normalized_bp_file == normalized_file and line in lines:
                return True
        
        return False
    
    def run_code(self, code: str, globals_dict: Dict[str, Any], filename: str = '<script>'):
        """
        Run code under debugger control.
        This method blocks until execution completes or is stopped.
        """
        import os
        import sys
        
        self.is_running = True
        self.is_paused = False
        self._exception = None
        self._continue_event.clear()
        self._step_mode = None  # Clear any step mode - run to breakpoints
        
        # Track this as user code (normalized)
        if filename != '<script>':
            normalized_filename = os.path.abspath(os.path.normpath(filename))
            self._user_files.add(normalized_filename)
            logger.info(f"Running user file: {normalized_filename}, tracked files: {self._user_files}")

        # Set workspace root to current working directory
        self._workspace_root = os.path.abspath(os.getcwd())
        
        def _run_with_continue(compiled_obj: Any):
            """Execute code under debugger, starting in continue mode."""
            self.reset()
            self.quitting = False
            self.set_continue()
            sys.settrace(self.trace_dispatch)
            try:
                exec(compiled_obj, globals_dict)
            finally:
                sys.settrace(None)
        
        try:
            # Compile the code
            compiled = compile(code, filename, 'exec')
            
            # Run under debugger to define functions (continue to breakpoints)
            _run_with_continue(compiled)
            
            # After defining functions, call the entry point
            # This matches the behavior in _run_script
            if 'main' in globals_dict and callable(globals_dict['main']):
                call_code = compile('main(ctx)', filename, 'exec')
                _run_with_continue(call_code)
            elif 'tick' in globals_dict and callable(globals_dict['tick']):
                call_code = compile('tick(ctx)', filename, 'exec')
                _run_with_continue(call_code)
            
        except Exception as e:
            self._exception = e
            logger.error(f"Script execution error: {e}")
            traceback.print_exc()
        finally:
            self.is_running = False
            self.is_paused = False
            
            # Notify completion
            if self.on_finish:
                try:
                    self.on_finish(self._exception)
                except Exception as e:
                    logger.error(f"Error in finish callback: {e}")
    
    def user_line(self, frame):
        """Called by bdb when execution stops at a line."""
        filename = frame.f_code.co_filename
        lineno = frame.f_lineno
        
        # Check breakpoint first
        has_breakpoint_here = self.has_breakpoint_at_line(filename, lineno)
        
        # Skip if not user code (unless there's a breakpoint here)
        is_user_code = self._is_user_code(filename)
        
        if not is_user_code and not has_breakpoint_here:
            return
        
        # If not stepping and no breakpoint here, do not stop
        if not has_breakpoint_here and not self._step_mode:
            return

        # Check if we should stop here
        should_stop = False
        
        # Check breakpoints
        if has_breakpoint_here:
            # Find the breakpoint and check condition (normalized comparison)
            import os
            normalized_filename = os.path.abspath(os.path.normpath(filename))
            for bp in self.breakpoints.values():
                normalized_bp_file = os.path.abspath(os.path.normpath(bp.file))
                if normalized_bp_file == normalized_filename and bp.line == lineno and bp.enabled:
                    bp.hit_count += 1
                    
                    # Evaluate condition if present
                    if bp.condition:
                        try:
                            if not eval(bp.condition, frame.f_globals, frame.f_locals):
                                continue
                        except Exception as e:
                            logger.warning(f"Breakpoint condition error: {e}")
                    
                    should_stop = True
                    break
        
        # Check step mode (only stop in user code when stepping)
        if is_user_code:
            if self._step_mode == 'into':
                should_stop = True
                self._step_mode = None
            elif self._step_mode == 'over':
                if frame == self._step_frame or frame.f_back == self._step_frame:
                    should_stop = True
                    self._step_mode = None
            elif self._step_mode == 'out':
                if frame.f_back == self._step_frame:
                    should_stop = True
                    self._step_mode = None
        
        if should_stop:
            self._current_frame = frame
            self.is_paused = True
            
            # Notify UI FIRST (before clearing/waiting)
            if self.on_break:
                try:
                    locals_dict = self._get_frame_locals(frame)
                    self.on_break(filename, lineno, locals_dict)
                except Exception as e:
                    logger.error(f"Error in break callback: {e}")
            
            # NOW prepare to wait (after UI callback)
            self._continue_event.clear()
            
            # Wait for continue/step command
            self._continue_event.wait()
            
            self.is_paused = False
    
    def user_return(self, frame, return_value):
        """Called when a function returns."""
        if self._step_mode == 'out' and frame == self._step_frame:
            # We're stepping out of this frame
            self._step_mode = 'into'  # Stop at next line
    
    def user_exception(self, frame, exc_info):
        """Called when an exception occurs."""
        self._exception = exc_info[1]

        filename = frame.f_code.co_filename
        lineno = frame.f_lineno
        has_breakpoint_here = self.has_breakpoint_at_line(filename, lineno)
        is_user_code = self._is_user_code(filename)

        # Skip pausing on exceptions outside user code unless a breakpoint is set
        if not is_user_code and not has_breakpoint_here:
            return
        
        # Pause at exception
        self._current_frame = frame
        self.is_paused = True
        
        # Notify UI first
        if self.on_break:
            try:
                locals_dict = self._get_frame_locals(frame)
                locals_dict['__exception__'] = str(exc_info[1])
                self.on_break(filename, lineno, locals_dict)
            except Exception as e:
                logger.error(f"Error in exception callback: {e}")
        
        # Prepare to wait (after callback)
        self._continue_event.clear()
        
        # Wait for user action
        self._continue_event.wait()
        
        self.is_paused = False
    
    def do_continue(self):
        """Continue execution until next breakpoint."""
        self._step_mode = None
        self._step_frame = None
        self._continue_event.set()
    
    def do_step_into(self):
        """Step into the next line (enter functions)."""
        self._step_mode = 'into'
        self._step_frame = self._current_frame
        self._continue_event.set()
    
    def do_step_over(self):
        """Step over the next line (don't enter functions)."""
        self._step_mode = 'over'
        self._step_frame = self._current_frame
        self._continue_event.set()
    
    def do_step_out(self):
        """Step out of the current function."""
        self._step_mode = 'out'
        self._step_frame = self._current_frame
        self._continue_event.set()
    
    def do_stop(self):
        """Stop execution."""
        self.set_quit()
        self._continue_event.set()
    
    def get_stack_trace(self) -> List[StackFrame]:
        """Get current stack trace."""
        if not self._current_frame:
            return []
        
        frames = []
        frame = self._current_frame
        
        while frame:
            frames.append(StackFrame(
                file=frame.f_code.co_filename,
                line=frame.f_lineno,
                function=frame.f_code.co_name,
                locals=self._get_frame_locals(frame),
                code_context=self._get_code_context(frame)
            ))
            frame = frame.f_back
        
        return frames
    
    def _get_frame_locals(self, frame) -> Dict[str, Any]:
        """Get local variables from a frame, safely converting to serializable format."""
        locals_dict = {}
        for name, value in frame.f_locals.items():
            try:
                # Try to get a string representation
                locals_dict[name] = repr(value)
            except Exception:
                locals_dict[name] = f"<{type(value).__name__}>"
        return locals_dict
    
    def _get_code_context(self, frame, context_lines: int = 3) -> List[str]:
        """Get code context around the current line."""
        try:
            filename = frame.f_code.co_filename
            lineno = frame.f_lineno
            
            with open(filename, 'r') as f:
                lines = f.readlines()
            
            start = max(0, lineno - context_lines - 1)
            end = min(len(lines), lineno + context_lines)
            
            return lines[start:end]
        except Exception:
            return []
    
    def evaluate_expression(self, expr: str) -> str:
        """Evaluate an expression in the current frame context."""
        if not self._current_frame:
            return "No active frame"
        
        try:
            result = eval(expr, self._current_frame.f_globals, self._current_frame.f_locals)
            return repr(result)
        except Exception as e:
            return f"Error: {e}"


class DebuggerThread(threading.Thread):
    """Thread for running scripts under debugger control."""
    
    def __init__(self, debugger: ScriptDebugger, code: str, context: Dict[str, Any], filename: str = '<script>'):
        super().__init__(daemon=True)
        self.debugger = debugger
        self.code = code
        self.context = context
        self.filename = filename
    
    def run(self):
        """Run the script in debugger."""
        self.debugger.run_code(self.code, self.context, self.filename)
