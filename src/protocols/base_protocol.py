from abc import ABC, abstractmethod
from typing import List, Optional, Callable
from src.models.device_models import DeviceConfig, Node, Signal

class BaseProtocol(ABC):
    """
    Abstract Base Class for all Protocol Implementations.
    Ensures a consistent interface for IEC 104, IEC 61850, etc.
    """
    
    def __init__(self, config: DeviceConfig):
        self.config = config
        self._callback: Optional[Callable[[Signal], None]] = None

    def set_data_callback(self, callback: Callable[[Signal], None]):
        """Sets the callback function to receive asynchronous data updates."""
        self._callback = callback

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to the remote device."""
        pass

    @abstractmethod
    def disconnect(self):
        """Close the connection."""
        pass

    @abstractmethod
    def discover(self) -> Node:
        """
        Perform discovery to build the Device Model (Nodes/Signals).
        Returns the Root Node of the device.
        """
        pass

    @abstractmethod
    def read_signal(self, signal: Signal) -> Signal:
        """Reads a specific signal synchronously."""
        pass

    # Control methods (optional, implement if protocol supports control)
    def send_command(self, signal: Signal, value, params: dict = None) -> bool:
        """
        High-level command sender (optional).
        Default: not implemented.
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support send_command")
    
    def select(self, signal: Signal, value=None, params: dict = None) -> bool:
        """SELECT phase for SBO control (optional)."""
        raise NotImplementedError(f"{self.__class__.__name__} does not support select")
    
    def operate(self, signal: Signal, value, params: dict = None) -> bool:
        """OPERATE phase for control (optional)."""
        raise NotImplementedError(f"{self.__class__.__name__} does not support operate")
    
    def cancel(self, signal: Signal) -> bool:
        """Cancel selection (optional)."""
        raise NotImplementedError(f"{self.__class__.__name__} does not support cancel")
    
    def _emit_update(self, signal: Signal):
        """Helper to invoke the data callback safely."""
        if self._callback:
            self._callback(signal)
