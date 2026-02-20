"""PLC-specific data models for IEC 61131-3 program management."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional, Set, Any


class IEC61131Language(Enum):
    """IEC 61131-3 programming languages."""
    STRUCTURED_TEXT = "ST"
    LADDER_DIAGRAM = "LD"
    FUNCTION_BLOCK_DIAGRAM = "FBD"
    SEQUENTIAL_FUNCTION_CHART = "SFC"
    INSTRUCTION_LIST = "IL"


class PLCMode(Enum):
    """PLC operating modes."""
    STOP = "stop"       # Not executing programs
    RUN = "run"         # Normal execution
    DEBUG = "debug"     # Execution with breakpoints
    FAULTED = "faulted" # Fatal error, safe state


class TaskType(Enum):
    """Task execution types."""
    CYCLIC = "cyclic"      # Fixed interval execution
    EVENT = "event"        # Triggered by external event
    INTERRUPT = "interrupt" # Hardware interrupt


class PLCDataType(Enum):
    """IEC 61131-3 elementary data types."""
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


class VariableQuality(Enum):
    """Variable quality status."""
    GOOD = "good"
    UNCERTAIN = "uncertain"
    BAD = "bad"


@dataclass
class PLCVariable:
    """PLC-typed variable with online monitoring."""
    name: str
    data_type: PLCDataType
    address: Optional[str] = None  # Memory address if direct
    
    # Properties
    initial_value: Any = None
    retain: bool = False  # Survives power cycle
    constant: bool = False
    
    # Online state
    current_value: Any = None
    quality: VariableQuality = VariableQuality.GOOD
    timestamp: Optional[datetime] = None
    forced: bool = False  # Manually forced value
    forced_value: Optional[Any] = None
    
    # Metadata
    comment: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'data_type': self.data_type.value,
            'address': self.address,
            'initial_value': self.initial_value,
            'retain': self.retain,
            'constant': self.constant,
            'comment': self.comment
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PLCVariable':
        data_type = PLCDataType.INT
        for dt in PLCDataType:
            if dt.value == data.get('data_type'):
                data_type = dt
                break
        
        return cls(
            name=data['name'],
            data_type=data_type,
            address=data.get('address'),
            initial_value=data.get('initial_value'),
            retain=data.get('retain', False),
            constant=data.get('constant', False),
            comment=data.get('comment', "")
        )


@dataclass
class VariableScope:
    """Collection of variables in a scope."""
    variables: List[PLCVariable] = field(default_factory=list)
    
    def get_variable(self, name: str) -> Optional[PLCVariable]:
        for var in self.variables:
            if var.name == name:
                return var
        return None
    
    def add_variable(self, variable: PLCVariable):
        # Remove existing if present
        self.variables = [v for v in self.variables if v.name != variable.name]
        self.variables.append(variable)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'variables': [v.to_dict() for v in self.variables]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VariableScope':
        scope = cls()
        for v_data in data.get('variables', []):
            scope.variables.append(PLCVariable.from_dict(v_data))
        return scope


@dataclass
class PLCProgram:
    """IEC 61131-3 program unit."""
    program_id: str
    name: str
    language: IEC61131Language
    source_code: str = ""
    compiled_code: Optional[bytes] = None
    
    # Execution binding
    parent_task_id: Optional[str] = None  # Task ID or None for main
    priority: int = 10
    
    # Variable scopes
    local_variables: VariableScope = field(default_factory=VariableScope)
    input_variables: VariableScope = field(default_factory=VariableScope)
    output_variables: VariableScope = field(default_factory=VariableScope)
    inout_variables: VariableScope = field(default_factory=VariableScope)
    
    # Metadata
    author: str = ""
    version: str = "1.0"
    last_modified: Optional[datetime] = None
    compiled_at: Optional[datetime] = None
    
    # Debugging state
    breakpoints: Set[int] = field(default_factory=set)  # Line numbers
    watch_expressions: List[str] = field(default_factory=list)
    
    # Runtime state
    enabled: bool = True
    running: bool = False

    def to_dict(self) -> Dict[str, Any]:
        import base64
        compiled_b64 = base64.b64encode(self.compiled_code).decode('utf-8') if self.compiled_code else None
        
        return {
            'program_id': self.program_id,
            'name': self.name,
            'language': self.language.value,
            'source_code': self.source_code,
            'compiled_code': compiled_b64,
            'parent_task_id': self.parent_task_id,
            'priority': self.priority,
            'local_variables': self.local_variables.to_dict(),
            'input_variables': self.input_variables.to_dict(),
            'output_variables': self.output_variables.to_dict(),
            'inout_variables': self.inout_variables.to_dict(),
            'author': self.author,
            'version': self.version,
            'enabled': self.enabled,
            'breakpoints': list(self.breakpoints),
            'watch_expressions': self.watch_expressions
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PLCProgram':
        import base64
        lang = IEC61131Language.STRUCTURED_TEXT
        for l in IEC61131Language:
            if l.value == data.get('language'):
                lang = l
                break
        
        compiled_code = None
        if data.get('compiled_code'):
            try:
                compiled_code = base64.b64decode(data['compiled_code'])
            except Exception:
                pass

        prog = cls(
            program_id=data['program_id'],
            name=data['name'],
            language=lang,
            source_code=data.get('source_code', ""),
            compiled_code=compiled_code,
            parent_task_id=data.get('parent_task_id'),
            priority=data.get('priority', 10),
            local_variables=VariableScope.from_dict(data.get('local_variables', {})),
            input_variables=VariableScope.from_dict(data.get('input_variables', {})),
            output_variables=VariableScope.from_dict(data.get('output_variables', {})),
            inout_variables=VariableScope.from_dict(data.get('inout_variables', {})),
            author=data.get('author', ""),
            version=data.get('version', "1.0"),
            enabled=data.get('enabled', True)
        )
        prog.breakpoints = set(data.get('breakpoints', []))
        prog.watch_expressions = data.get('watch_expressions', [])
        return prog


@dataclass
class PLCTask:
    """IEC 61131-3 task for cyclic/event execution."""
    task_id: str
    name: str
    task_type: TaskType
    
    # Scheduling
    priority: int = 10  # 0 (highest) to 31 (lowest)
    interval_ms: Optional[float] = None  # For cyclic tasks
    event_source: Optional[str] = None  # For event-driven tasks
    
    # Associated programs
    program_ids: List[str] = field(default_factory=list)
    
    # Runtime metrics
    actual_cycle_time_ms: float = 0.0
    max_cycle_time_ms: float = 0.0
    overruns: int = 0
    
    # State
    enabled: bool = True
    running: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            'task_id': self.task_id,
            'name': self.name,
            'task_type': self.task_type.value,
            'priority': self.priority,
            'interval_ms': self.interval_ms,
            'event_source': self.event_source,
            'program_ids': self.program_ids,
            'enabled': self.enabled
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PLCTask':
        t_type = TaskType.CYCLIC
        for tt in TaskType:
            if tt.value == data.get('task_type'):
                t_type = tt
                break
        
        return cls(
            task_id=data['task_id'],
            name=data['name'],
            task_type=t_type,
            priority=data.get('priority', 10),
            interval_ms=data.get('interval_ms'),
            event_source=data.get('event_source'),
            program_ids=data.get('program_ids', []),
            enabled=data.get('enabled', True)
        )


@dataclass
class PLCFault:
    """PLC fault/error information."""
    fault_id: str
    severity: str  # "ERROR", "WARNING", "CRITICAL"
    message: str
    program_id: Optional[str] = None
    line_number: Optional[int] = None
    timestamp: Optional[datetime] = None


@dataclass
class PLCDeviceExtension:
    """Extended attributes for PLC-capable devices."""
    plc_type: str = "Simulated"  # "Simulated", "Modicon", "Siemens S7", etc.
    runtime_version: str = "1.0.0"
    scan_time_ms: float = 0.0  # Actual measured scan time
    
    # Program organization
    programs: List[PLCProgram] = field(default_factory=list)
    tasks: List[PLCTask] = field(default_factory=list)
    global_variables: VariableScope = field(default_factory=VariableScope)
    
    # Runtime state
    operating_mode: PLCMode = PLCMode.STOP
    last_fault: Optional[PLCFault] = None
    uptime_seconds: float = 0.0
    
    def get_program(self, program_id: str) -> Optional[PLCProgram]:
        for prog in self.programs:
            if prog.program_id == program_id:
                return prog
        return None
    
    def get_task(self, task_id: str) -> Optional[PLCTask]:
        for task in self.tasks:
            if task.task_id == task_id:
                return task
        return None
    
    def add_program(self, program: PLCProgram):
        # Remove existing if present
        self.programs = [p for p in self.programs if p.program_id != program.program_id]
        self.programs.append(program)
    
    def remove_program(self, program_id: str):
        self.programs = [p for p in self.programs if p.program_id != program_id]
    
    def add_task(self, task: PLCTask):
        # Remove existing if present
        self.tasks = [t for t in self.tasks if t.task_id != task.task_id]
        self.tasks.append(task)
    
    def remove_task(self, task_id: str):
        self.tasks = [t for t in self.tasks if t.task_id != task_id]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'plc_type': self.plc_type,
            'runtime_version': self.runtime_version,
            'programs': [p.to_dict() for p in self.programs],
            'tasks': [t.to_dict() for t in self.tasks],
            'global_variables': self.global_variables.to_dict(),
            'operating_mode': self.operating_mode.value
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PLCDeviceExtension':
        ext = cls(
            plc_type=data.get('plc_type', "Simulated"),
            runtime_version=data.get('runtime_version', "1.0.0"),
            global_variables=VariableScope.from_dict(data.get('global_variables', {}))
        )
        
        for p_data in data.get('programs', []):
            ext.programs.append(PLCProgram.from_dict(p_data))
            
        for t_data in data.get('tasks', []):
            ext.tasks.append(PLCTask.from_dict(t_data))
            
        mode = PLCMode.STOP
        for m in PLCMode:
            if m.value == data.get('operating_mode'):
                mode = m
                break
        ext.operating_mode = mode
        
        return ext


@dataclass
class CompileError:
    """Compilation error."""
    line: int
    column: int
    message: str
    severity: str = "ERROR"  # ERROR, WARNING


@dataclass
class CompileResult:
    """Result of program compilation."""
    success: bool
    bytecode: Optional[bytes] = None
    warnings: List[CompileError] = field(default_factory=list)
    errors: List[CompileError] = field(default_factory=list)


# ===== Phase 2: Function Blocks and Functions =====

@dataclass
class PLCFunction:
    """User-defined function (stateless)."""
    function_id: str
    name: str
    language: IEC61131Language
    source_code: str = ""
    compiled_code: Optional[bytes] = None
    
    # Signature
    input_parameters: VariableScope = field(default_factory=VariableScope)
    output_parameters: VariableScope = field(default_factory=VariableScope)
    return_type: Optional[PLCDataType] = None
    
    # Metadata
    description: str = ""
    last_modified: Optional[datetime] = None


@dataclass
class PLCFunctionBlock:
    """Function block definition (stateful)."""
    fb_id: str
    name: str
    language: IEC61131Language
    source_code: str = ""
    compiled_code: Optional[bytes] = None
    
    # Signature
    input_variables: VariableScope = field(default_factory=VariableScope)
    output_variables: VariableScope = field(default_factory=VariableScope)
    inout_variables: VariableScope = field(default_factory=VariableScope)
    static_variables: VariableScope = field(default_factory=VariableScope)  # Internal state
    
    # Metadata
    description: str = ""
    version: str = "1.0"
    vendor: str = "User"  # "User", "System", "Vendor Name"
    last_modified: Optional[datetime] = None


@dataclass
class FBInstance:
    """Instance of a function block with state."""
    instance_id: str
    instance_name: str
    fb_type_id: str  # References PLCFunctionBlock.fb_id
    
    # Instance state (copy of static variables)
    state_variables: Dict[str, Any] = field(default_factory=dict)
    
    # Current I/O values
    input_values: Dict[str, Any] = field(default_factory=dict)
    output_values: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    parent_program_id: str = ""
    enabled: bool = True


# ===== Phase 2: Debugging Models =====

class DebugState(Enum):
    """Debug execution states."""
    RUNNING = "running"
    PAUSED = "paused"
    STEP_INTO = "step_into"
    STEP_OVER = "step_over"
    STEP_OUT = "step_out"


@dataclass
class Breakpoint:
    """Program breakpoint."""
    breakpoint_id: str
    program_id: str
    line: int
    enabled: bool = True
    condition: Optional[str] = None  # Conditional breakpoint expression
    hit_count: int = 0


@dataclass
class CallStackFrame:
    """Call stack frame for debugging."""
    program_id: str
    program_name: str
    line: int
    variables: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WatchExpression:
    """Watch expression for debugging."""
    expression: str
    value: Any = None
    error: Optional[str] = None
    last_updated: Optional[datetime] = None

