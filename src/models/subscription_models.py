from enum import Enum
from dataclasses import dataclass

class SubscriptionMode(Enum):
    READ_POLLING = "READ_POLLING" # Periodic MMS Read (ST/MX)
    REPORTING = "REPORTING"       # Buffered/Unbuffered Reports (RCB)
    ON_DEMAND = "ON_DEMAND"       # Single-shot manual read

@dataclass(frozen=True)
class IECSubscription:
    """
    Auhtoritative subscription definition.
    Immutable to ensure hashability for set storage.
    """
    device: str
    mms_path: str   # Full object path (IED/LD/LN.DO.DA)
    fc: str         # Functional Constraint (ST, MX)
    mode: SubscriptionMode
    source: str     # Origin of subscription: "live_data", "historian", etc.
