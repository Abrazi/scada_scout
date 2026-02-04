"""
Modbus RTU Transport Layer
Provides abstraction for different physical transports (Serial, RTU-over-TCP)
"""
import logging
import time
from abc import ABC, abstractmethod
from typing import Optional, Tuple
from dataclasses import dataclass
import threading

logger = logging.getLogger(__name__)

# Try to import pyserial
try:
    import serial
    import serial.tools.list_ports
    HAS_PYSERIAL = True
except ImportError:
    HAS_PYSERIAL = False
    serial = None

# Socket for RTU-over-TCP
import socket


@dataclass
class SerialConfig:
    """Serial port configuration"""
    port: str                    # e.g., COM3, /dev/ttyUSB0
    baudrate: int = 9600
    bytesize: int = 8            # 5, 6, 7, 8
    parity: str = 'N'            # N(one), E(ven), O(dd), M(ark), S(pace)
    stopbits: float = 1.0        # 1, 1.5, 2
    timeout: float = 1.0         # Read timeout in seconds
    write_timeout: float = 1.0   # Write timeout in seconds
    
    def to_pyserial_parity(self) -> str:
        """Convert parity character to pyserial constant"""
        if not HAS_PYSERIAL:
            return self.parity
        
        parity_map = {
            'N': serial.PARITY_NONE,
            'E': serial.PARITY_EVEN,
            'O': serial.PARITY_ODD,
            'M': serial.PARITY_MARK,
            'S': serial.PARITY_SPACE
        }
        return parity_map.get(self.parity.upper(), serial.PARITY_NONE)
    
    def to_pyserial_stopbits(self) -> float:
        """Convert stopbits to pyserial constant"""
        if not HAS_PYSERIAL:
            return self.stopbits
            
        if self.stopbits == 1:
            return serial.STOPBITS_ONE
        elif self.stopbits == 1.5:
            return serial.STOPBITS_ONE_POINT_FIVE
        elif self.stopbits == 2:
            return serial.STOPBITS_TWO
        return serial.STOPBITS_ONE


class BaseTransport(ABC):
    """Abstract base class for Modbus RTU transports"""
    
    def __init__(self):
        self._is_open = False
        self._lock = threading.RLock()  # Reentrant lock for thread safety
    
    @abstractmethod
    def open(self) -> bool:
        """Open the transport connection"""
        pass
    
    @abstractmethod
    def close(self):
        """Close the transport connection"""
        pass
    
    @abstractmethod
    def send_frame(self, frame: bytes) -> bool:
        """Send a complete RTU frame"""
        pass
    
    @abstractmethod
    def receive_frame(self, timeout: Optional[float] = None) -> Optional[bytes]:
        """Receive a complete RTU frame with timeout"""
        pass
    
    @abstractmethod
    def flush(self):
        """Flush input and output buffers"""
        pass
    
    @property
    def is_open(self) -> bool:
        """Check if transport is open"""
        return self._is_open


class SerialTransport(BaseTransport):
    """
    Serial transport for RS-485 and USB-to-RS-485 adapters
    Cross-platform support using pyserial
    """
    
    def __init__(self, config: SerialConfig):
        super().__init__()
        self.config = config
        self._serial: Optional[serial.Serial] = None
        
        if not HAS_PYSERIAL:
            logger.error("pyserial not installed. Install with: pip install pyserial")
            raise ImportError("pyserial library required for serial transport")
    
    def open(self) -> bool:
        """Open serial port"""
        with self._lock:
            if self._is_open:
                logger.warning(f"Serial port {self.config.port} already open")
                return True
            
            try:
                logger.info(f"Opening serial port {self.config.port} at {self.config.baudrate} baud")
                
                self._serial = serial.Serial(
                    port=self.config.port,
                    baudrate=self.config.baudrate,
                    bytesize=self.config.bytesize,
                    parity=self.config.to_pyserial_parity(),
                    stopbits=self.config.to_pyserial_stopbits(),
                    timeout=self.config.timeout,
                    write_timeout=self.config.write_timeout,
                    inter_byte_timeout=None  # We handle framing ourselves
                )
                
                # Flush buffers to ensure clean state
                self._serial.reset_input_buffer()
                self._serial.reset_output_buffer()
                
                self._is_open = True
                logger.info(f"Serial port {self.config.port} opened successfully")
                return True
                
            except serial.SerialException as e:
                logger.error(f"Failed to open serial port {self.config.port}: {e}")
                self._is_open = False
                return False
            except Exception as e:
                logger.error(f"Unexpected error opening serial port: {e}")
                self._is_open = False
                return False
    
    def close(self):
        """Close serial port"""
        with self._lock:
            if self._serial and self._is_open:
                try:
                    self._serial.close()
                    logger.info(f"Serial port {self.config.port} closed")
                except Exception as e:
                    logger.error(f"Error closing serial port: {e}")
                finally:
                    self._serial = None
                    self._is_open = False
    
    def send_frame(self, frame: bytes) -> bool:
        """Send RTU frame over serial"""
        with self._lock:
            if not self._is_open or not self._serial:
                logger.error("Serial port not open")
                return False
            
            try:
                # Ensure clean state before transmission
                self._serial.reset_output_buffer()
                
                # Send frame
                bytes_written = self._serial.write(frame)
                
                # Ensure all data is transmitted
                self._serial.flush()
                
                if bytes_written != len(frame):
                    logger.warning(f"Incomplete write: {bytes_written}/{len(frame)} bytes")
                    return False
                
                logger.debug(f"Sent {len(frame)} bytes: {frame.hex()}")
                return True
                
            except serial.SerialTimeoutException:
                logger.error("Serial write timeout")
                return False
            except Exception as e:
                logger.error(f"Error sending frame: {e}")
                return False
    
    def receive_frame(self, timeout: Optional[float] = None) -> Optional[bytes]:
        """
        Receive RTU frame with proper inter-byte timing
        
        RTU frames are variable length, so we need to:
        1. Wait for first byte (with timeout)
        2. Continue reading until 3.5 character silence
        3. Return complete frame or None
        """
        with self._lock:
            if not self._is_open or not self._serial:
                logger.error("Serial port not open")
                return None
            
            try:
                # Set timeout for first byte
                original_timeout = self._serial.timeout
                if timeout is not None:
                    self._serial.timeout = timeout
                
                # Wait for first byte
                first_byte = self._serial.read(1)
                if not first_byte:
                    # Timeout waiting for frame
                    return None
                
                # Calculate inter-byte timeout (1.5 character times is typical)
                # For high baud rates, use minimum timeout
                char_time = self._calculate_char_time()
                inter_byte_timeout = max(char_time * 1.5, 0.001)  # Minimum 1ms
                
                self._serial.timeout = inter_byte_timeout
                
                # Read remaining bytes until silence
                frame = bytearray(first_byte)
                silent_count = 0
                max_silent = 2  # Number of timeouts to consider frame complete
                
                while silent_count < max_silent:
                    byte = self._serial.read(1)
                    if byte:
                        frame.extend(byte)
                        silent_count = 0  # Reset silence counter
                    else:
                        silent_count += 1
                
                # Restore original timeout
                self._serial.timeout = original_timeout
                
                if len(frame) > 0:
                    logger.debug(f"Received {len(frame)} bytes: {bytes(frame).hex()}")
                    return bytes(frame)
                
                return None
                
            except serial.SerialException as e:
                logger.error(f"Serial receive error: {e}")
                return None
            except Exception as e:
                logger.error(f"Unexpected error receiving frame: {e}")
                return None
    
    def flush(self):
        """Flush serial port buffers"""
        with self._lock:
            if self._serial and self._is_open:
                try:
                    self._serial.reset_input_buffer()
                    self._serial.reset_output_buffer()
                except Exception as e:
                    logger.debug(f"Error flushing buffers: {e}")
    
    def _calculate_char_time(self) -> float:
        """Calculate time for one character transmission"""
        # Character = 1 start + data bits + parity bit + stop bits
        bits_per_char = 1 + self.config.bytesize
        
        if self.config.parity != 'N':
            bits_per_char += 1
        
        bits_per_char += self.config.stopbits
        
        char_time = bits_per_char / self.config.baudrate
        return char_time


class RTUoverTCPTransport(BaseTransport):
    """
    RTU-over-TCP transport
    Sends RTU frames (with CRC) over TCP socket
    This is NOT Modbus TCP (which has MBAP header)
    """
    
    def __init__(self, host: str, port: int, timeout: float = 1.0):
        super().__init__()
        self.host = host
        self.port = port
        self.timeout = timeout
        self._socket: Optional[socket.socket] = None
    
    def open(self) -> bool:
        """Open TCP connection"""
        with self._lock:
            if self._is_open:
                logger.warning(f"TCP connection to {self.host}:{self.port} already open")
                return True
            
            try:
                logger.info(f"Connecting to {self.host}:{self.port} (RTU over TCP)")
                
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.settimeout(self.timeout)
                self._socket.connect((self.host, self.port))
                
                self._is_open = True
                logger.info(f"Connected to {self.host}:{self.port}")
                return True
                
            except socket.timeout:
                logger.error(f"Connection timeout to {self.host}:{self.port}")
                self._is_open = False
                return False
            except socket.error as e:
                logger.error(f"Socket error connecting to {self.host}:{self.port}: {e}")
                self._is_open = False
                return False
            except Exception as e:
                logger.error(f"Unexpected error connecting: {e}")
                self._is_open = False
                return False
    
    def close(self):
        """Close TCP connection"""
        with self._lock:
            if self._socket and self._is_open:
                try:
                    self._socket.close()
                    logger.info(f"Disconnected from {self.host}:{self.port}")
                except Exception as e:
                    logger.error(f"Error closing socket: {e}")
                finally:
                    self._socket = None
                    self._is_open = False
    
    def send_frame(self, frame: bytes) -> bool:
        """Send RTU frame over TCP"""
        with self._lock:
            if not self._is_open or not self._socket:
                logger.error("Socket not open")
                return False
            
            try:
                self._socket.sendall(frame)
                logger.debug(f"Sent {len(frame)} bytes: {frame.hex()}")
                return True
                
            except socket.timeout:
                logger.error("Socket send timeout")
                return False
            except socket.error as e:
                logger.error(f"Socket send error: {e}")
                return False
            except Exception as e:
                logger.error(f"Unexpected error sending frame: {e}")
                return False
    
    def receive_frame(self, timeout: Optional[float] = None) -> Optional[bytes]:
        """
        Receive RTU frame over TCP
        TCP is stream-based, so we need to detect frame boundaries
        """
        with self._lock:
            if not self._is_open or not self._socket:
                logger.error("Socket not open")
                return None
            
            try:
                # Set timeout
                original_timeout = self._socket.gettimeout()
                if timeout is not None:
                    self._socket.settimeout(timeout)
                
                # Minimum RTU frame: slave(1) + func(1) + crc(2) = 4 bytes
                # Read in chunks and detect silence to find frame boundary
                frame = bytearray()
                chunk_size = 256
                silence_time = 0.01  # 10ms silence indicates frame end
                
                start_time = time.perf_counter()
                last_recv_time = start_time
                
                while True:
                    try:
                        chunk = self._socket.recv(chunk_size)
                        if chunk:
                            frame.extend(chunk)
                            last_recv_time = time.perf_counter()
                        else:
                            # Connection closed
                            break
                        
                        # Check for silence (frame complete)
                        if time.perf_counter() - last_recv_time > silence_time:
                            break
                            
                    except socket.timeout:
                        # If we have data, consider frame complete
                        if len(frame) >= 4:
                            break
                        # Otherwise, timeout waiting for frame
                        return None
                
                # Restore original timeout
                self._socket.settimeout(original_timeout)
                
                if len(frame) >= 4:
                    logger.debug(f"Received {len(frame)} bytes: {bytes(frame).hex()}")
                    return bytes(frame)
                
                return None
                
            except socket.error as e:
                logger.error(f"Socket receive error: {e}")
                return None
            except Exception as e:
                logger.error(f"Unexpected error receiving frame: {e}")
                return None
    
    def flush(self):
        """Flush socket buffers (not really applicable to TCP)"""
        # TCP streams don't have a flush concept like serial
        # We can drain the receive buffer if needed
        if self._socket and self._is_open:
            try:
                self._socket.setblocking(False)
                while True:
                    try:
                        self._socket.recv(1024)
                    except socket.error:
                        break
                self._socket.setblocking(True)
            except Exception as e:
                logger.debug(f"Error flushing socket: {e}")


def list_serial_ports() -> list:
    """
    List available serial ports
    Returns list of tuples: (device, description)
    """
    if not HAS_PYSERIAL:
        logger.warning("pyserial not installed, cannot list ports")
        return []
    
    try:
        ports = serial.tools.list_ports.comports()
        return [(p.device, p.description) for p in sorted(ports)]
    except Exception as e:
        logger.error(f"Error listing serial ports: {e}")
        return []


def get_standard_baudrates() -> list:
    """Return list of standard Modbus RTU baud rates"""
    return [
        300, 600, 1200, 2400, 4800, 9600,
        14400, 19200, 28800, 38400, 57600,
        115200, 230400, 460800, 921600
    ]
