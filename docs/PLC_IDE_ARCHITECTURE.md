# Professional PLC IDE Architecture for SCADA Scout

## Executive Summary

This document specifies a **commercial-grade PLC development environment** integrated into SCADA Scout's Device Explorer, providing IEC 61131-3 program management, real-time debugging, and industrial-strength execution control comparable to leading automation platforms.

---

## 1. System Architecture

### 1.1 Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Device Explorer (UI)                      │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────────┐    │
│  │ PLC Device │──│ Program Tree │──│ Task Hierarchy   │    │
│  └────────────┘  └──────────────┘  └──────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      PLC IDE Layer                           │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │ Code Editor  │  │ Debugger     │  │ Variable Watch  │   │
│  │ (IEC 61131)  │  │ Controller   │  │ Manager         │   │
│  └──────────────┘  └──────────────┘  └─────────────────┘   │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │ Compiler     │  │ Cross-Ref    │  │ Online Monitor  │   │
│  │ Frontend     │  │ Analyzer     │  │ Interface       │   │
│  └──────────────┘  └──────────────┘  └─────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 PLC Runtime Adapter Layer                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Runtime Protocol Bridge (Modbus, IEC 61131, etc.)  │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   PLC Runtime Engine                         │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │ Scan Engine  │  │ Task Manager │  │ Memory Manager  │   │
│  └──────────────┘  └──────────────┘  └─────────────────┘   │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │ IEC 61131    │  │ Debug Agent  │  │ State Machine   │   │
│  │ Interpreter  │  │ (Online)     │  │ Controller      │   │
│  └──────────────┘  └──────────────┘  └─────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Separation of Concerns

**IDE Layer (Non-Real-Time)**
- Code editing, syntax highlighting, validation
- Project management, file operations
- User interface, visualizations
- Debug command generation

**Runtime Layer (Real-Time)**
- Deterministic scan execution
- IEC 61131-3 program execution
- Task scheduling and prioritization
- Safe state transitions

**Bridge Layer (Protocol)**
- IDE ↔ Runtime communication
- Debug protocol (breakpoints, variable inspection)
- Program upload/download
- Online change management

---

## 2. Data Models

### 2.1 PLC Device Model

```python
@dataclass
class PLCDevice:
    """Extended device model for PLC-specific capabilities."""
    device_id: str
    name: str
    device_type: DeviceType  # PLC_MODBUS, PLC_IEC61131, etc.
    connection_config: ConnectionConfig
    
    # PLC-specific attributes
    plc_type: str  # "Simulated", "Modicon", "Siemens S7", etc.
    runtime_version: str
    scan_time_ms: float  # Actual measured scan time
    
    # Program organization
    programs: List[PLCProgram]
    tasks: List[PLCTask]
    global_variables: VariableScope
    
    # Runtime state
    operating_mode: PLCMode  # RUN, STOP, DEBUG, FAULTED
    last_fault: Optional[PLCFault]
    uptime_seconds: float
```

### 2.2 Program Model

```python
@dataclass
class PLCProgram:
    """IEC 61131-3 program unit."""
    program_id: str
    name: str
    language: IEC61131Language  # ST, LD, FBD, SFC, IL
    source_code: str
    compiled_code: Optional[bytes]
    
    # Execution binding
    parent_task: Optional[str]  # Task ID or None for main
    priority: int
    
    # Variable scopes
    local_variables: VariableScope
    input_variables: VariableScope
    output_variables: VariableScope
    inout_variables: VariableScope
    
    # Metadata
    author: str
    version: str
    last_modified: datetime
    compiled_at: Optional[datetime]
    
    # Debugging state
    breakpoints: Set[int]  # Line numbers
    watch_expressions: List[str]

class IEC61131Language(Enum):
    STRUCTURED_TEXT = "ST"
    LADDER_DIAGRAM = "LD"
    FUNCTION_BLOCK_DIAGRAM = "FBD"
    SEQUENTIAL_FUNCTION_CHART = "SFC"
    INSTRUCTION_LIST = "IL"
```

### 2.3 Task Model

```python
@dataclass
class PLCTask:
    """IEC 61131-3 task for cyclic/event execution."""
    task_id: str
    name: str
    task_type: TaskType  # CYCLIC, EVENT, INTERRUPT
    
    # Scheduling
    priority: int  # 0 (highest) to 31 (lowest)
    interval_ms: Optional[float]  # For cyclic tasks
    event_source: Optional[str]  # For event-driven tasks
    
    # Associated programs
    program_ids: List[str]
    
    # Runtime metrics
    actual_cycle_time_ms: float
    max_cycle_time_ms: float
    overruns: int
    
    # State
    enabled: bool
    running: bool

class TaskType(Enum):
    CYCLIC = "cyclic"  # Fixed interval execution
    EVENT = "event"    # Triggered by external event
    INTERRUPT = "interrupt"  # Hardware interrupt
```

### 2.4 Variable Model

```python
@dataclass
class PLCVariable:
    """PLC-typed variable with online monitoring."""
    name: str
    data_type: PLCDataType
    address: Optional[str]  # Memory address if direct
    
    # Properties
    initial_value: Any
    retain: bool  # Survives power cycle
    constant: bool
    
    # Online state
    current_value: Any
    quality: VariableQuality  # GOOD, UNCERTAIN, BAD
    timestamp: datetime
    forced: bool  # Manually forced value
    forced_value: Optional[Any]

class PLCDataType(Enum):
    BOOL = "BOOL"
    BYTE = "BYTE"
    WORD = "WORD"
    DWORD = "DWORD"
    LWORD = "LWORD"
    SINT = "SINT"
    INT = "INT"
    DINT = "DINT"
    LINT = "LINT"
    USINT = "USINT"
    UINT = "UINT"
    UDINT = "UDINT"
    ULINT = "ULINT"
    REAL = "REAL"
    LREAL = "LREAL"
    TIME = "TIME"
    DATE = "DATE"
    TIME_OF_DAY = "TIME_OF_DAY"
    DATE_AND_TIME = "DATE_AND_TIME"
    STRING = "STRING"
    WSTRING = "WSTRING"
    ARRAY = "ARRAY"
    STRUCT = "STRUCT"
```

---

## 3. Execution Model

### 3.1 Scan Cycle (Cyclic Tasks)

```
┌─────────────────────────────────────────────────────────┐
│                     PLC Scan Cycle                       │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │  1. Read Inputs (I/O Update)                     │  │
│  │     - Physical inputs → Input image table        │  │
│  │     - Network inputs (Modbus, IEC 61850, etc.)   │  │
│  └──────────────────────────────────────────────────┘  │
│                         │                                │
│                         ▼                                │
│  ┌──────────────────────────────────────────────────┐  │
│  │  2. Execute Program Logic                        │  │
│  │     - Task priority order                        │  │
│  │     - Program POUs (ST, LD, FBD, SFC)           │  │
│  │     - Function blocks, functions                 │  │
│  └──────────────────────────────────────────────────┘  │
│                         │                                │
│                         ▼                                │
│  ┌──────────────────────────────────────────────────┐  │
│  │  3. Write Outputs (I/O Update)                   │  │
│  │     - Output image table → Physical outputs      │  │
│  │     - Network outputs (Modbus writes, etc.)      │  │
│  └──────────────────────────────────────────────────┘  │
│                         │                                │
│                         ▼                                │
│  ┌──────────────────────────────────────────────────┐  │
│  │  4. Housekeeping                                 │  │
│  │     - Diagnostics update                         │  │
│  │     - Communication processing                   │  │
│  │     - Debug command handling                     │  │
│  └──────────────────────────────────────────────────┘  │
│                         │                                │
│                         └──────────┐                     │
│                                    ▼                     │
│                            ┌───────────────┐             │
│                            │  Wait for     │             │
│                            │  Next Cycle   │             │
│                            └───────────────┘             │
└─────────────────────────────────────────────────────────┘
```

### 3.2 Operating Modes

```python
class PLCMode(Enum):
    STOP = "stop"       # Not executing programs
    RUN = "run"         # Normal execution
    DEBUG = "debug"     # Execution with breakpoints
    FAULTED = "faulted" # Fatal error, safe state

class ModeTransition:
    """Safe mode transition controller."""
    
    ALLOWED_TRANSITIONS = {
        PLCMode.STOP: [PLCMode.RUN, PLCMode.DEBUG],
        PLCMode.RUN: [PLCMode.STOP, PLCMode.DEBUG],
        PLCMode.DEBUG: [PLCMode.STOP, PLCMode.RUN],
        PLCMode.FAULTED: [PLCMode.STOP]  # Requires reset
    }
    
    @staticmethod
    def can_transition(from_mode: PLCMode, to_mode: PLCMode) -> bool:
        return to_mode in ModeTransition.ALLOWED_TRANSITIONS.get(from_mode, [])
    
    @staticmethod
    def transition(plc: PLCDevice, to_mode: PLCMode) -> bool:
        """Execute safe mode transition with outputs held."""
        if not ModeTransition.can_transition(plc.operating_mode, to_mode):
            return False
        
        # Pre-transition: hold outputs safe
        if to_mode == PLCMode.STOP:
            plc.hold_outputs_safe()
        
        # Atomic mode switch
        plc.operating_mode = to_mode
        
        # Post-transition: initialize state
        if to_mode == PLCMode.RUN:
            plc.initialize_program_state()
        elif to_mode == PLCMode.DEBUG:
            plc.enable_debug_hooks()
        
        return True
```

---

## 4. Debugging Architecture

### 4.1 Debug Protocol

```python
class DebugCommand(Enum):
    SET_BREAKPOINT = "set_bp"
    CLEAR_BREAKPOINT = "clear_bp"
    STEP_OVER = "step_over"
    STEP_INTO = "step_into"
    STEP_OUT = "step_out"
    CONTINUE = "continue"
    PAUSE = "pause"
    READ_VARIABLE = "read_var"
    WRITE_VARIABLE = "write_var"
    READ_CALL_STACK = "read_stack"

@dataclass
class DebugEvent:
    """Event from runtime to IDE."""
    event_type: DebugEventType
    program_id: str
    line_number: int
    variables: Dict[str, Any]
    call_stack: List[StackFrame]
    timestamp: datetime

class DebugEventType(Enum):
    BREAKPOINT_HIT = "breakpoint_hit"
    STEP_COMPLETE = "step_complete"
    PROGRAM_FAULT = "program_fault"
    WATCH_TRIGGERED = "watch_triggered"

@dataclass
class StackFrame:
    """Call stack frame for debugging."""
    program_name: str
    function_name: Optional[str]
    line_number: int
    local_variables: Dict[str, Any]
```

### 4.2 Task-Safe Breakpoints

```python
class BreakpointManager:
    """Ensures breakpoints don't violate real-time constraints."""
    
    def __init__(self, max_break_duration_ms: float = 100):
        self.max_break_duration_ms = max_break_duration_ms
        self._breakpoints: Dict[str, Set[int]] = {}  # program_id -> line numbers
        self._watchdog = BreakpointWatchdog(max_break_duration_ms)
    
    def set_breakpoint(self, program_id: str, line: int) -> bool:
        """Set breakpoint only if task-safe."""
        task = self._get_program_task(program_id)
        if task and task.task_type == TaskType.INTERRUPT:
            return False  # Cannot break in ISR
        
        if program_id not in self._breakpoints:
            self._breakpoints[program_id] = set()
        self._breakpoints[program_id].add(line)
        return True
    
    def on_breakpoint_hit(self, program_id: str, line: int):
        """Handle breakpoint hit with watchdog."""
        self._watchdog.start()
        
        # Notify IDE
        self._notify_ide(DebugEvent(
            event_type=DebugEventType.BREAKPOINT_HIT,
            program_id=program_id,
            line_number=line,
            variables=self._capture_variables(program_id),
            call_stack=self._capture_stack(),
            timestamp=datetime.now()
        ))
        
        # Block execution until IDE releases or watchdog fires
        self._wait_for_continue_or_timeout()
    
    def _wait_for_continue_or_timeout(self):
        """Block with watchdog protection."""
        while not self._continue_requested and not self._watchdog.expired():
            time.sleep(0.001)
        
        if self._watchdog.expired():
            # Force continue to prevent scan overrun
            self._auto_continue()
```

### 4.3 Inline Variable Display

```python
class InlineVariableMonitor:
    """Real-time variable value overlay in editor."""
    
    def __init__(self, editor: CodeEditor, plc_device: PLCDevice):
        self.editor = editor
        self.plc = plc_device
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._refresh_values)
        self._update_timer.start(100)  # 10Hz update rate
    
    def _refresh_values(self):
        """Update inline variable displays."""
        if self.plc.operating_mode not in [PLCMode.RUN, PLCMode.DEBUG]:
            return
        
        # Parse visible code for variable references
        visible_lines = self.editor.get_visible_lines()
        variables = self._extract_variables(visible_lines)
        
        # Batch read from runtime
        values = self.plc.read_variables_batch(variables)
        
        # Render inline
        for var_name, value in values.items():
            line_numbers = self._find_variable_lines(var_name, visible_lines)
            for line in line_numbers:
                self.editor.add_inline_annotation(
                    line, 
                    f" ({self._format_value(value)})",
                    color=QColor(120, 120, 120)
                )
    
    def _format_value(self, value: Any) -> str:
        """Format value for inline display."""
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        elif isinstance(value, float):
            return f"{value:.3f}"
        elif isinstance(value, int):
            return str(value)
        else:
            return repr(value)[:20]  # Truncate long values
```

---

## 5. Compiler Integration

### 5.1 Compiler Frontend

```python
class IEC61131Compiler:
    """Compile IEC 61131-3 source to runtime bytecode."""
    
    def compile(self, program: PLCProgram) -> CompileResult:
        """Compile program with full semantic analysis."""
        try:
            # Lexical analysis
            tokens = self._tokenize(program.source_code)
            
            # Syntax analysis
            ast = self._parse(tokens, program.language)
            
            # Semantic analysis
            self._type_check(ast, program)
            self._scope_check(ast, program)
            
            # Code generation
            bytecode = self._generate_bytecode(ast)
            
            # Optimization
            bytecode = self._optimize(bytecode)
            
            return CompileResult(
                success=True,
                bytecode=bytecode,
                warnings=[],
                errors=[]
            )
        except CompileError as e:
            return CompileResult(
                success=False,
                bytecode=None,
                warnings=[],
                errors=[e]
            )
    
    def _type_check(self, ast: AST, program: PLCProgram):
        """Strong type checking per IEC 61131-3."""
        for node in ast.walk():
            if isinstance(node, AssignmentNode):
                lhs_type = self._infer_type(node.lhs, program)
                rhs_type = self._infer_type(node.rhs, program)
                
                if not self._is_compatible(lhs_type, rhs_type):
                    raise TypeError(
                        f"Type mismatch: cannot assign {rhs_type} to {lhs_type}"
                    )

@dataclass
class CompileResult:
    success: bool
    bytecode: Optional[bytes]
    warnings: List[CompileWarning]
    errors: List[CompileError]
```

### 5.2 Online Change

```python
class OnlineChangeManager:
    """Safe online program modification."""
    
    def apply_online_change(
        self, 
        program_id: str, 
        new_code: str
    ) -> OnlineChangeResult:
        """Apply code change to running PLC."""
        
        # Compile new code
        compile_result = self.compiler.compile(PLCProgram(
            program_id=program_id,
            source_code=new_code,
            ...
        ))
        
        if not compile_result.success:
            return OnlineChangeResult(
                success=False,
                error="Compilation failed"
            )
        
        # Verify change is safe (no variable type changes, etc.)
        if not self._is_change_safe(program_id, compile_result.bytecode):
            return OnlineChangeResult(
                success=False,
                error="Unsafe change: would corrupt variable state"
            )
        
        # Apply atomically at scan boundary
        self.plc.apply_code_change_at_scan_boundary(
            program_id,
            compile_result.bytecode
        )
        
        return OnlineChangeResult(success=True)
```

---

## 6. UI/UX Design

### 6.1 Device Explorer Integration

```
Device Explorer
├── PLC_Device_1 (Simulated)  [RUN] ●
│   ├── Configuration
│   ├── Programs ▼
│   │   ├── Main.st           [Cyclic, 10ms]
│   │   ├── AlarmHandler.st   [Event: E_FAULT]
│   │   └── PumpControl.st    [Cyclic, 100ms]
│   ├── Tasks ▼
│   │   ├── FastTask (Priority 0, 10ms) ⚡
│   │   └── SlowTask (Priority 10, 100ms) ⚡
│   ├── Global Variables
│   ├── Runtime Diagnostics
│   │   ├── Scan Time: 3.2ms / 10ms
│   │   ├── Overruns: 0
│   │   └── Uptime: 2d 14h 32m
│   └── Automation Scripts ▼
│       ├── Python Scripts...
│       └── IEC 61131 Scripts...
│
└── PLC_Device_2 (S7-1200)  [STOP] ○
    └── ...
```

### 6.2 Code Editor Features

- **Syntax Highlighting**: Language-specific (ST, LD rendering, etc.)
- **Autocompletion**: Context-aware (task scope, globals, FB instances)
- **Inline Values**: Real-time variable display (MotorSpeed `(1450)`)
- **Error Markers**: Red underlines for compile errors
- **Breakpoint Gutter**: Visual breakpoint indicators
- **Call Stack Panel**: Active when debugging
- **Variable Watch**: Persistent watch table
- **Cross-Reference**: Jump-to-definition, find-all-references

---

## 7. Safety & Constraints

### 7.1 Real-Time Guarantees

1. **Scan Determinism**: Debug operations must not cause scan overruns
2. **Priority Preservation**: High-priority tasks always execute first
3. **Watchdog Protection**: Automatic recovery from debug hangs

### 7.2 Fail-Safe Behavior

1. **Communication Loss**: PLC continues executing last downloaded program
2. **Debug Disconnect**: Breakpoints automatically disabled, execution continues
3. **Fault State**: Outputs held safe, controlled recovery only

### 7.3 Access Control

1. **Online Change**: Requires elevated permissions
2. **Force Variables**: Logged and auditable
3. **Mode Changes**: Operator acknowledgment required

---

## 8. Implementation Phases

### Phase 1: Foundation
- PLC device model extension
- Basic ST editor with syntax highlighting
- Compiler frontend (ST only)
- STOP/RUN mode control

### Phase 2: Execution
- Cyclic task execution
- Variable read/write via Modbus
- Simple monitoring (no breakpoints)

### Phase 3: Debugging
- Breakpoint support
- Step execution
- Call stack and variable inspection
- Inline variable display

### Phase 4: Advanced
- Online change
- Multi-language support (LD, FBD)
- Task profiling and diagnostics
- Cross-reference tools

---

## 9. Technology Stack

### IDE Components
- **Editor**: Modified `CodeEditor` with IEC 61131 lexer
- **Compiler**: Custom ST parser + type checker
- **Debugger**: Protocol-based debug agent

### Runtime Options
1. **Internal Simulated Runtime**: Python-based interpreter for testing
2. **External Runtime Bridge**: Connect to real PLC via Modbus/OPC UA
3. **Native Runtime**: Future libiec61131 integration

### Communication
- **Debug Protocol**: JSON-RPC over TCP or shared memory
- **Variable Access**: Modbus, IEC 61850 MMS, or proprietary

---

## 10. Comparison to Industry Standards

| Feature | SCADA Scout PLC IDE | Siemens TIA Portal | Rockwell Studio 5000 |
|---------|---------------------|-------------------|----------------------|
| IEC 61131-3 Support | ST (Phase 1) | All 5 languages | ST, LD, FBD |
| Online Change | Yes (Phase 4) | Yes | Yes |
| Inline Variables | Yes | Yes | Yes |
| Cyclic Tasks | Yes | Yes | Yes |
| Event Tasks | Yes (Phase 2) | Yes | Yes |
| Integrated SCADA | Yes (native) | WinCC integration | FactoryTalk View |

**Quality Target**: Match or exceed mid-tier commercial PLCs (ABB, Schneider M221/M251)

---

## Conclusion

This architecture delivers a **professional-grade PLC IDE** within SCADA Scout, enabling:
- Industrial-strength IEC 61131-3 development
- Real-time debugging without compromising scan determinism
- Seamless integration with existing device management
- Scalable architecture for future enhancements

The phased approach ensures incremental value delivery while maintaining code quality and safety standards required for industrial automation systems.
