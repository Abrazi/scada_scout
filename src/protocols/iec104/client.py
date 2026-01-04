from datetime import datetime
import random
import threading
import time
from typing import List

from src.protocols.base_protocol import BaseProtocol
from src.models.device_models import DeviceConfig, Node, Signal, SignalType, SignalQuality

class IEC104Client(BaseProtocol):
    """
    Simulated IEC 60870-5-104 Client.
    Generates realistic looking telemetry data for testing.
    """
    def __init__(self, config: DeviceConfig):
        super().__init__(config)
        self._connected = False
        self._sim_thread = None
        self._stop_sim = False
        self._signals: List[Signal] = []

    def connect(self) -> bool:
        """Simulates connection delay and success."""
        time.sleep(0.5) # Fake network delay
        self._connected = True
        self._start_simulation()
        return True

    def disconnect(self):
        self._stop_sim = True
        if self._sim_thread:
            self._sim_thread.join()
        self._connected = False

    def discover(self) -> Node:
        """Returns a fixed structure mimicking a Substation RTU."""
        root = Node(name="RTU_Root")
        
        # M_ME_NC_1 (Measured Values)
        measurements = Node(name="Measurements")
        
        sig_v = Signal(name="Voltage_L1", address="1001", signal_type=SignalType.ANALOG, description="Busbar Voltage")
        sig_c = Signal(name="Current_L1", address="1002", signal_type=SignalType.ANALOG, description="Feeder Current")
        sig_p = Signal(name="ActivePower", address="1003", signal_type=SignalType.ANALOG, description="MW")
        
        measurements.signals.extend([sig_v, sig_c, sig_p])
        self._signals.extend([sig_v, sig_c, sig_p])
        
        # M_SP_NA_1 (Single Points)
        status = Node(name="Status")
        sig_cb = Signal(name="CircuitBreaker", address="2001", signal_type=SignalType.BINARY, description="Main CB Position")
        
        status.signals.append(sig_cb)
        self._signals.append(sig_cb)
        
        root.children.extend([measurements, status])
        return root

    def read_signal(self, signal: Signal) -> Signal:
        """Returns the current cached value."""
        return signal

    def _start_simulation(self):
        """Starts a background thread to generate random data."""
        self._stop_sim = False
        self._sim_thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self._sim_thread.start()

    def _simulation_loop(self):
        """Generates random changes."""
        while not self._stop_sim:
            if not self._signals:
                time.sleep(1)
                continue
                
            # Pick a random signal to update
            sig = random.choice(self._signals)
            
            # Update value based on type
            if sig.signal_type == SignalType.ANALOG:
                # Add random noise
                current = float(sig.value) if sig.value is not None else 100.0
                sig.value = round(current + random.uniform(-1.5, 1.5), 2)
            elif sig.signal_type == SignalType.BINARY:
                # Flip status occasionally
                if random.random() > 0.95:
                    sig.value = not bool(sig.value)
            
            sig.timestamp = datetime.now()
            sig.quality = SignalQuality.GOOD
            
            # Emit update
            self._emit_update(sig)
            
            # Sleep a bit (simulate typical traffic)
            time.sleep(0.1)
