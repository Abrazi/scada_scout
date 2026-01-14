from enum import Enum, auto
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

class ControlModel(Enum):
    STATUS_ONLY = 0
    DIRECT_NORMAL = 1
    SBO_NORMAL = 2
    DIRECT_ENHANCED = 3
    SBO_ENHANCED = 4
    
    @property
    def is_sbo(self):
        return self in [ControlModel.SBO_NORMAL, ControlModel.SBO_ENHANCED]
    
    @property
    def is_enhanced(self):
        return self in [ControlModel.DIRECT_ENHANCED, ControlModel.SBO_ENHANCED]

class ControlState(Enum):
    IDLE = auto()
    SELECT_READY = auto() # Ready to be selected
    SELECTED = auto()     # SBO succeeded, timer running
    OPERATING = auto()    # Operate sent, waiting for confirm
    OPERATED = auto()     # Operation successful
    FAILED = auto()       # Last operation failed

@dataclass
class ControlObjectRuntime:
    """
    Runtime state tracker for an IEC 61850 Control Object (DO).
    """
    object_reference: str # Full DO path: LD/LN.DO
    ctl_model: ControlModel = ControlModel.DIRECT_NORMAL
    
    # State tracking
    state: ControlState = ControlState.IDLE
    last_select_time: Optional[datetime] = None
    last_operate_time: Optional[datetime] = None
    last_error: str = ""
    
    # Selection parameters
    sbo_timeout: int = 10000 # Default MMS timeout in ms
    originator_cat: int = 2 # Station
    originator_cat: int = 2 # Station
    originator_id: str = "ScadaScout"
    sbo_reference: str = "" # Path to SBO or SBOw attribute
    
    def reset(self):
        self.state = ControlState.IDLE
        self.last_error = ""

    def update_from_ctl_model_int(self, val: int):
        try:
            self.ctl_model = ControlModel(val)
        except ValueError:
            self.ctl_model = ControlModel.DIRECT_NORMAL
