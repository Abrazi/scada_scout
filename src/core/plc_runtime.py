"""Simulated PLC runtime for executing IEC 61131-3 programs with debugging support."""
import logging
import threading
import time
from typing import Dict, Optional, Any, List, Callable
from datetime import datetime

from src.models.plc_models import (
    PLCDeviceExtension, PLCProgram, PLCTask, PLCMode, 
    TaskType, PLCFault, PLCVariable, VariableQuality,
    Breakpoint, DebugState, CallStackFrame, WatchExpression
)

logger = logging.getLogger(__name__)


class DebugEngine:
    """Debugging engine for PLC programs."""
    
    def __init__(self, device: Optional[PLCDeviceExtension] = None, log_func: Optional[Callable] = None):
        self.device = device
        self.log_func = log_func
        self.breakpoints: Dict[str, List[Breakpoint]] = {}  # program_id -> List[Breakpoint]
        self.debug_state: DebugState = DebugState.RUNNING
        self.current_program_id: Optional[str] = None
        self.current_line: Optional[int] = None
        self.call_stack: List[CallStackFrame] = []
        self.watch_expressions: List[WatchExpression] = []
        
        # Step control
        self._step_event = threading.Event()
        self._step_requested: Optional[DebugState] = None
        
        # Callbacks
        self._on_breakpoint_hit: Optional[Callable] = None
        self._on_step_complete: Optional[Callable] = None
    
    def add_breakpoint(self, program_id: str, line: int, condition: Optional[str] = None) -> Breakpoint:
        """Add a breakpoint to a program."""
        bp = Breakpoint(
            breakpoint_id=f"BP_{program_id}_{line}",
            program_id=program_id,
            line=line,
            condition=condition
        )
        
        if program_id not in self.breakpoints:
            self.breakpoints[program_id] = []
        
        # Remove existing breakpoint at same line
        self.breakpoints[program_id] = [b for b in self.breakpoints[program_id] if b.line != line]
        self.breakpoints[program_id].append(bp)
        
        return bp
    
    def remove_breakpoint(self, program_id: str, line: int):
        """Remove a breakpoint."""
        if program_id in self.breakpoints:
            self.breakpoints[program_id] = [b for b in self.breakpoints[program_id] if b.line != line]
    
    def toggle_breakpoint(self, program_id: str, line: int):
        """Toggle breakpoint enabled state."""
        if program_id in self.breakpoints:
            for bp in self.breakpoints[program_id]:
                if bp.line == line:
                    bp.enabled = not bp.enabled
                    return
        # Add if not exists
        self.add_breakpoint(program_id, line)
    
    def clear_breakpoints(self, program_id: Optional[str] = None):
        """Clear breakpoints."""
        if program_id:
            self.breakpoints[program_id] = []
        else:
            self.breakpoints.clear()
    
    def get_breakpoints(self, program_id: Optional[str] = None) -> List[Breakpoint]:
        """Get breakpoints for a program or all breakpoints."""
        if program_id:
            return self.breakpoints.get(program_id, [])
        else:
            # Return all breakpoints from all programs
            all_bps = []
            for bps in self.breakpoints.values():
                all_bps.extend(bps)
            return all_bps
    
    def check_breakpoint(self, program_id: str, line: int, context: Dict[str, Any]) -> bool:
        """Check if breakpoint should halt execution."""
        if program_id not in self.breakpoints:
            return False
        
        for bp in self.breakpoints[program_id]:
            if bp.line == line and bp.enabled:
                # Check condition if present
                if bp.condition:
                    try:
                        if eval(bp.condition, context):
                            bp.hit_count += 1
                            return True
                    except:
                        pass  # Condition evaluation failed, ignore
                else:
                    bp.hit_count += 1
                    return True
        
        return False
    
    def step_into(self):
        """Step into next statement."""
        self._step_requested = DebugState.STEP_INTO
        self._step_event.set()
    
    def step_over(self):
        """Step over current statement."""
        self._step_requested = DebugState.STEP_OVER
        self._step_event.set()
    
    def step_out(self):
        """Step out of current function."""
        self._step_requested = DebugState.STEP_OUT
        self._step_event.set()
    
    def continue_execution(self):
        """Continue normal execution."""
        self.debug_state = DebugState.RUNNING
        self._step_event.set()
    
    def pause(self):
        """Pause execution at next statement."""
        self.debug_state = DebugState.PAUSED
    
    def wait_for_step(self):
        """Wait for step command (used by runtime)."""
        if self.debug_state != DebugState.RUNNING:
            self._step_event.wait()
            self._step_event.clear()
            
            if self._step_requested:
                self.debug_state = self._step_requested
                self._step_requested = None
    
    def add_watch(self, expression: str, program_id: Optional[str] = None):
        """Add watch expression."""
        watch = WatchExpression(expression=expression)
        self.watch_expressions.append(watch)
        return watch
    
    def remove_watch(self, expression: str):
        """Remove watch expression."""
        self.watch_expressions = [w for w in self.watch_expressions if w.expression != expression]
    
    def get_watches(self) -> List[WatchExpression]:
        """Get all watch expressions."""
        return self.watch_expressions
    
    def update_watches(self, context: Dict[str, Any]):
        """Update all watch expressions."""
        for watch in self.watch_expressions:
            try:
                watch.value = eval(watch.expression, context)
                watch.error = None
                watch.last_updated = datetime.now()
            except Exception as e:
                watch.value = None
                watch.error = str(e)
                watch.last_updated = datetime.now()
    
    def push_call_frame(self, program_id: str, program_name: str, line: int, variables: Dict[str, Any]):
        """Push a call stack frame."""
        frame = CallStackFrame(
            program_id=program_id,
            program_name=program_name,
            line=line,
            variables=variables.copy()
        )
        self.call_stack.append(frame)
    
    def pop_call_frame(self):
        """Pop a call stack frame."""
        if self.call_stack:
            self.call_stack.pop()
    
    def set_on_breakpoint_hit(self, callback: Callable):
        """Set callback for breakpoint hits."""
        self._on_breakpoint_hit = callback
    
    def set_on_step_complete(self, callback: Callable):
        """Set callback for step completions."""
        self._on_step_complete = callback


class PLCRuntime:
    """Simulated PLC runtime with debugging support."""
    
    def __init__(self, device_extension: PLCDeviceExtension, event_logger=None):
        self.device = device_extension
        self.event_logger = event_logger
        
        self._running = False
        self._scan_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Execution context (simplified Python namespace for ST interpretation)
        self._global_context: Dict[str, Any] = {}
        self._program_contexts: Dict[str, Dict[str, Any]] = {}
        
        # Debugging support
        self.debug_engine = DebugEngine(device_extension, self._log)
        
        # Online change support
        self._pending_code_change: Optional[Dict[str, str]] = None  # program_id -> new_source
        self._code_change_lock = threading.Lock()
        
        # Verbose logging
        self.verbose_logging = False
    
    def start(self) -> bool:
        """Start PLC runtime (transition to RUN mode)."""
        if self.device.operating_mode == PLCMode.RUN:
            return True
        
        if self.device.operating_mode == PLCMode.FAULTED:
            self._log("error", "Cannot start PLC in FAULTED state. Reset required.")
            return False
        
        self.device.operating_mode = PLCMode.RUN
        self._running = True
        self._stop_event.clear()
        
        # Initialize variable contexts
        self._initialize_contexts()
        
        # Start scan thread
        self._scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self._scan_thread.start()
        
        self._log("info", f"PLC Runtime started ({self.device.plc_type})")
        return True
    
    def start_debug(self) -> bool:
        """Start PLC runtime in debug mode (transition to DEBUG mode)."""
        if self.device.operating_mode == PLCMode.DEBUG:
            return True
        
        if self.device.operating_mode == PLCMode.FAULTED:
            self._log("error", "Cannot start PLC in FAULTED state. Reset required.")
            return False
        
        self.device.operating_mode = PLCMode.DEBUG
        self._running = True
        self._stop_event.clear()
        
        # Initialize variable contexts
        self._initialize_contexts()
        
        # Initialize debug engine
        self.debug_engine = DebugEngine(self.device, self._log)
        
        # Start scan thread
        self._scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self._scan_thread.start()
        
        self._log("info", f"PLC Runtime started in DEBUG mode ({self.device.plc_type})")
        return True
    
    def stop(self) -> bool:
        """Stop PLC runtime (transition to STOP mode)."""
        if self.device.operating_mode == PLCMode.STOP:
            return True
        
        self._running = False
        self._stop_event.set()
        
        if self._scan_thread:
            self._scan_thread.join(timeout=2.0)
        
        # Hold outputs safe
        self._hold_outputs_safe()
        
        self.device.operating_mode = PLCMode.STOP
        self._log("info", "PLC Runtime stopped")
        return True
    
    def reset(self) -> bool:
        """Reset PLC from FAULTED state."""
        if self.device.operating_mode == PLCMode.FAULTED:
            self.device.operating_mode = PLCMode.STOP
            self.device.last_fault = None
            self._log("info", "PLC reset from fault")
            return True
        return False
    
    def online_change(self, program_id: str, new_source_code: str) -> bool:
        """Apply online change to running program (hot-reload)."""
        program = self.device.get_program(program_id)
        if not program:
            self._log("error", f"Program {program_id} not found")
            return False
        
        # Compile new code
        from src.core.st_compiler import STCompiler
        compiler = STCompiler()
        
        # Create temporary program for compilation
        temp_program = PLCProgram(
            program_id=program_id,
            name=program.name,
            language=program.language,
            source_code=new_source_code
        )
        
        result = compiler.compile(temp_program)
        
        if not result.success:
            error_msgs = "; ".join([f"Line {e.line}: {e.message}" for e in result.errors])
            self._log("error", f"Online change failed - compilation errors: {error_msgs}")
            return False
        
        # Apply change atomically
        with self._code_change_lock:
            # Store old state for rollback
            old_source = program.source_code
            old_bytecode = program.compiled_code
            old_input_vars = program.input_variables
            old_output_vars = program.output_variables
            old_local_vars = program.local_variables
            
            try:
                # Apply new code
                program.source_code = new_source_code
                program.compiled_code = temp_program.compiled_code
                program.input_variables = temp_program.input_variables
                program.output_variables = temp_program.output_variables
                program.local_variables = temp_program.local_variables
                
                # Re-initialize context for this program (preserve existing values where possible)
                old_ctx = self._program_contexts.get(program_id, {})
                new_ctx = {}
                
                # Copy values for variables that still exist
                all_new_vars = (temp_program.input_variables.variables + 
                               temp_program.output_variables.variables + 
                               temp_program.local_variables.variables)
                
                for var in all_new_vars:
                    if var.name in old_ctx:
                        # Keep existing value
                        new_ctx[var.name] = old_ctx[var.name]
                    else:
                        # Initialize new variable
                        new_ctx[var.name] = var.initial_value or self._default_value(var.data_type)
                
                self._program_contexts[program_id] = new_ctx
                
                self._log("info", f"Online change successful for program {program.name}")
                return True
                
            except Exception as e:
                # Rollback on error
                program.source_code = old_source
                program.compiled_code = old_bytecode
                program.input_variables = old_input_vars
                program.output_variables = old_output_vars
                program.local_variables = old_local_vars
                
                self._log("error", f"Online change rollback: {e}")
                return False
    
    def _initialize_contexts(self):
        """Initialize execution contexts for all programs."""
        # Global variables
        self._global_context = {}
        for var in self.device.global_variables.variables:
            value = var.initial_value if var.initial_value is not None else self._default_value(var.data_type)
            self._global_context[var.name] = value
            var.current_value = value  # Set current value
        
        # Program-local contexts
        self._program_contexts = {}
        for program in self.device.programs:
            if not program.enabled:
                continue
            
            ctx = {}
            # Add all variable scopes
            for var in program.input_variables.variables:
                value = var.initial_value if var.initial_value is not None else self._default_value(var.data_type)
                ctx[var.name] = value
                var.current_value = value  # Set current value
            for var in program.output_variables.variables:
                value = var.initial_value if var.initial_value is not None else self._default_value(var.data_type)
                ctx[var.name] = value
                var.current_value = value  # Set current value
            for var in program.local_variables.variables:
                value = var.initial_value if var.initial_value is not None else self._default_value(var.data_type)
                ctx[var.name] = value
                var.current_value = value  # Set current value
            
            self._program_contexts[program.program_id] = ctx
    
    def _default_value(self, data_type):
        """Return default value for a data type."""
        from src.models.plc_models import PLCDataType
        if data_type == PLCDataType.BOOL:
            return False
        elif 'INT' in data_type.value:
            return 0
        elif 'REAL' in data_type.value:
            return 0.0
        else:
            return None
    
    def _scan_loop(self):
        """Main PLC scan loop."""
        start_time = time.time()
        scan_count = 0
        
        while self._running and not self._stop_event.is_set():
            scan_start = time.time()
            scan_count += 1
            
            try:
                # Execute all enabled cyclic tasks by priority
                tasks = sorted(
                    [t for t in self.device.tasks if t.enabled and t.task_type == TaskType.CYCLIC],
                    key=lambda t: t.priority
                )
                
                if self.verbose_logging and scan_count % 10 == 0:
                    total_progs = len(self.device.programs)
                    assigned_progs = sum(len(t.program_ids) for t in tasks)
                    self._log("info", f"[SCAN {scan_count}] Executing {len(tasks)} tasks, {total_progs} programs total ({assigned_progs} assigned to tasks)")
                
                for task in tasks:
                    self._execute_task(task)
                
                # Update uptime
                self.device.uptime_seconds = time.time() - start_time
                
                # Measure scan time
                scan_duration = (time.time() - scan_start) * 1000  # ms
                self.device.scan_time_ms = scan_duration
                
                # Sleep to maintain minimum scan rate (default 10ms)
                min_scan_time = 0.010  # 10ms
                sleep_time = max(0, min_scan_time - (time.time() - scan_start))
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
            except Exception as e:
                logger.exception("PLC scan loop error")
                self._handle_fault(f"Scan loop error: {e}")
                break
    
    def _execute_task(self, task: PLCTask):
        """Execute all programs in a task."""
        task.running = True
        task_start = time.time()
        
        if self.verbose_logging:
            if len(task.program_ids) == 0:
                self._log("warning", f"  [TASK] {task.name}: ⚠️ NO PROGRAMS ASSIGNED! (program_ids is empty)")
            else:
                self._log("info", f"  [TASK] {task.name}: Starting with {len(task.program_ids)} programs")
        
        try:
            for program_id in task.program_ids:
                program = self.device.get_program(program_id)
                if program and program.enabled and program.compiled_code:
                    if self.verbose_logging:
                        self._log("info", f"    [PROG] {program.name}: Executing...")
                    self._execute_program(program)
                elif program and self.verbose_logging:
                    if not program.enabled:
                        self._log("warning", f"    [PROG] {program.name}: SKIPPED (disabled)")
                    elif not program.compiled_code:
                        self._log("warning", f"    [PROG] {program.name}: SKIPPED (not compiled)")
            
            # Update task metrics
            cycle_time = (time.time() - task_start) * 1000  # ms
            task.actual_cycle_time_ms = cycle_time
            task.max_cycle_time_ms = max(task.max_cycle_time_ms, cycle_time)
            
            if task.interval_ms and cycle_time > task.interval_ms:
                task.overruns += 1
        
        finally:
            task.running = False
    
    def _execute_program(self, program: PLCProgram):
        """Execute a single program with enhanced AST-based execution."""
        program.running = True
        
        try:
            # Push call frame for debugging
            if self.device.operating_mode == PLCMode.DEBUG:
                self.debug_engine.push_call_frame(program.program_id, program.name, 1, {})
            
            # Get program context
            ctx = self._program_contexts.get(program.program_id, {})
            
            # Merge global context
            exec_context = {**self._global_context, **ctx}
            
            # Debug logging
            logger.debug(f"[EXEC] Program {program.name}: context before = {ctx}")
            
            # Decode bytecode
            if program.compiled_code:
                import json
                try:
                    bytecode_data = json.loads(program.compiled_code.decode('utf-8'))
                    if isinstance(bytecode_data, dict) and 'source' in bytecode_data:
                        # Version 2.0 bytecode with AST
                        source = bytecode_data['source']
                        ast = bytecode_data.get('ast')
                    else:
                        # Legacy bytecode (just source)
                        source = program.compiled_code.decode('utf-8')
                        ast = None
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # Legacy bytecode
                    source = program.compiled_code.decode('utf-8')
                    ast = None
            else:
                source = ""
                ast = None
            
            # Extract only the executable statements (skip VAR blocks)
            executable_lines = []
            in_var_block = False
            for line in source.split('\n'):
                line_stripped = line.strip().upper()
                if line_stripped.startswith('VAR'):
                    in_var_block = True
                elif line_stripped == 'END_VAR':
                    in_var_block = False
                elif not in_var_block and not line_stripped.startswith('PROGRAM') and not line_stripped.startswith('END_PROGRAM'):
                    executable_lines.append(line)
            
            executable_code = '\n'.join(executable_lines)
            
            # Convert ST syntax to Python
            python_code = self._st_to_python(executable_code)
            
            # Execute
            exec(python_code, exec_context, exec_context)
            
            # Debug logging
            logger.debug(f"[EXEC] Program {program.name}: context after = {exec_context}")
            
            # Save updated context back (excluding built-ins)
            self._program_contexts[program.program_id] = {
                k: v for k, v in exec_context.items()
                if not k.startswith('__') and not callable(v)
            }
            
            # Update variable values (input, output, local)
            all_vars = (program.input_variables.variables + 
                       program.output_variables.variables + 
                       program.local_variables.variables)
            
            updated_count = 0
            var_summary = []
            for var in all_vars:
                if var.name in exec_context:
                    old_value = var.current_value
                    var.current_value = exec_context[var.name]
                    var.quality = VariableQuality.GOOD
                    var.timestamp = datetime.now()
                    updated_count += 1
                    
                    if self.verbose_logging and old_value != var.current_value:
                        var_summary.append(f"{var.name}={var.current_value}")
                    
                    logger.debug(f"[EXEC] Updated {var.name} = {var.current_value}")
            
            if self.verbose_logging and var_summary:
                self._log("info", f"      [VARS] {', '.join(var_summary)}")
            
            logger.debug(f"[EXEC] Updated {updated_count}/{len(all_vars)} variables")
            
            # Update watches if in DEBUG mode
            if self.device.operating_mode == PLCMode.DEBUG:
                self.debug_engine.update_watches(exec_context)
        
        except Exception as e:
            logger.exception(f"Error executing program {program.name}")
            self._handle_fault(f"Program {program.name} error: {e}", program.program_id)
        
        finally:
            # Pop call frame
            if self.device.operating_mode == PLCMode.DEBUG:
                self.debug_engine.pop_call_frame()
            program.running = False
    
    def _st_to_python(self, st_code: str) -> str:
        """Convert ST syntax to Python with control flow support."""
        python_code = st_code
        
        # ST assignment (:=) to Python (=)
        python_code = python_code.replace(':=', '=')
        
        # ST comparison (<>) to Python (!=)
        python_code = python_code.replace('<>', '!=')
        
        # ST boolean keywords
        python_code = python_code.replace(' AND ', ' and ')
        python_code = python_code.replace(' OR ', ' or ')
        python_code = python_code.replace(' NOT ', ' not ')
        python_code = python_code.replace('TRUE', 'True')
        python_code = python_code.replace('FALSE', 'False')
        
        # Control flow keywords (ST to Python)
        lines = []
        indent_level = 0
        for line in python_code.split('\n'):
            line_upper = line.strip().upper()
            
            # Handle IF statements
            if line_upper.startswith('IF '):
                lines.append('    ' * indent_level + line.strip().replace('IF ', 'if ').replace(' THEN', ':'))
                indent_level += 1
            elif line_upper.startswith('ELSIF '):
                indent_level -= 1
                lines.append('    ' * indent_level + line.strip().replace('ELSIF ', 'elif ').replace(' THEN', ':'))
                indent_level += 1
            elif line_upper == 'ELSE':
                indent_level -= 1
                lines.append('    ' * indent_level + 'else:')
                indent_level += 1
            elif line_upper == 'END_IF;':
                indent_level -= 1
            
            # Handle FOR loops
            elif line_upper.startswith('FOR '):
                # FOR i := 1 TO 10 BY 2 DO -> for i in range(1, 10+1, 2):
                match = line.strip()
                match = match.replace('FOR ', '').replace(' DO', '').replace(';', '')
                parts = match.split(' TO ')
                if len(parts) == 2:
                    var_init = parts[0].strip()  # i = 1
                    var_name = var_init.split('=')[0].strip()
                    start_val = var_init.split('=')[1].strip()
                    
                    end_parts = parts[1].split(' BY ')
                    end_val = end_parts[0].strip()
                    step_val = end_parts[1].strip() if len(end_parts) > 1 else '1'
                    
                    lines.append('    ' * indent_level + f'for {var_name} in range({start_val}, {end_val}+1, {step_val}):')
                    indent_level += 1
            elif line_upper == 'END_FOR;':
                indent_level -= 1
            
            # Handle WHILE loops
            elif line_upper.startswith('WHILE '):
                lines.append('    ' * indent_level + line.strip().replace('WHILE ', 'while ').replace(' DO', ':'))
                indent_level += 1
            elif line_upper == 'END_WHILE;':
                indent_level -= 1
            
            # Handle REPEAT loops
            elif line_upper == 'REPEAT':
                # REPEAT..UNTIL -> while True: ... if condition: break
                lines.append('    ' * indent_level + 'while True:')
                indent_level += 1
            elif line_upper.startswith('UNTIL '):
                condition = line.strip().replace('UNTIL ', '').replace('END_REPEAT;', '').replace(';', '')
                lines.append('    ' * indent_level + f'if {condition}:')
                lines.append('    ' * (indent_level + 1) + 'break')
                indent_level -= 1
            elif line_upper == 'END_REPEAT;':
                pass  # Already handled by UNTIL
            
            # Handle CASE statements
            elif line_upper.startswith('CASE '):
                selector = line.strip().replace('CASE ', '').replace(' OF', '')
                lines.append('    ' * indent_level + f'_case_selector = {selector}')
                lines.append('    ' * indent_level + 'if False:')
                lines.append('    ' * (indent_level + 1) + 'pass')
                indent_level += 1
            elif ':' in line and not line_upper.startswith('END_CASE') and indent_level > 0:
                # Case branch: value: statements
                case_value = line.split(':')[0].strip()
                lines.append('    ' * indent_level + f'elif _case_selector == {case_value}:')
            elif line_upper == 'END_CASE;':
                indent_level -= 1
            
            # Regular statements
            else:
                # Remove semicolons
                clean_line = line.replace(';', '')
                if clean_line.strip():
                    lines.append('    ' * indent_level + clean_line.strip())
        
        return '\n'.join(lines)
    
    def _hold_outputs_safe(self):
        """Set all outputs to safe state."""
        # For simulation, just set outputs to zero/false
        for program in self.device.programs:
            for var in program.output_variables.variables:
                var.current_value = self._default_value(var.data_type)
                var.quality = VariableQuality.GOOD
    
    def _handle_fault(self, message: str, program_id: Optional[str] = None):
        """Handle PLC fault."""
        self.device.operating_mode = PLCMode.FAULTED
        self.device.last_fault = PLCFault(
            fault_id=f"FAULT_{int(time.time())}",
            severity="CRITICAL",
            message=message,
            program_id=program_id,
            timestamp=datetime.now()
        )
        self._log("error", f"PLC FAULT: {message}")
        self.stop()
    
    def _log(self, level: str, message: str):
        """Log to event logger or standard logger."""
        if self.event_logger:
            try:
                if level == "info":
                    self.event_logger.info("PLC Runtime", message)
                elif level == "warning":
                    self.event_logger.warning("PLC Runtime", message)
                elif level == "error":
                    self.event_logger.error("PLC Runtime", message)
                return
            except Exception:
                pass
        logger.info(message)
