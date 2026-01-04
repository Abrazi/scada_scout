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

    # TODO: Add write_signal methods later
    
    def _emit_update(self, signal: Signal):
        """Helper to invoke the data callback safely."""
        if self._callback:
            self._callback(signal)
