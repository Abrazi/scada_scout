"""
Modbus RTU Timing Manager
Handles inter-frame gaps, character times, and timeouts per Modbus RTU specification
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ModbusRTUTiming:
    """
    Manages timing calculations for Modbus RTU
    
    Key specifications:
    - Inter-frame gap: 3.5 character times (minimum silent period between frames)
    - Character time: Time to transmit one character at given baud rate
    - For baud rates > 19200, use fixed 1.75ms inter-frame gap
    """
    
    def __init__(self, baudrate: int, bytesize: int = 8, 
                 parity: str = 'N', stopbits: float = 1.0):
        """
        Initialize timing calculator
        
        Args:
            baudrate: Baud rate (bits per second)
            bytesize: Data bits per character (5-8)
            parity: Parity ('N', 'E', 'O', 'M', 'S')
            stopbits: Stop bits (1, 1.5, 2)
        """
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        
        # Calculate derived values
        self._char_time = self._calculate_character_time()
        self._inter_frame_gap = self._calculate_inter_frame_gap()
        
        logger.debug(f"RTU Timing: baudrate={baudrate}, char_time={self._char_time*1000:.3f}ms, "
                    f"inter_frame_gap={self._inter_frame_gap*1000:.3f}ms")
    
    def _calculate_character_time(self) -> float:
        """
        Calculate time (in seconds) to transmit one character
        
        Character format:
        - 1 start bit
        - data bits (5-8)
        - parity bit (if enabled)
        - stop bits (1, 1.5, or 2)
        
        Returns:
            Character time in seconds
        """
        # Start bit (always 1)
        bits_per_char = 1
        
        # Data bits
        bits_per_char += self.bytesize
        
        # Parity bit (if not None)
        if self.parity and self.parity.upper() != 'N':
            bits_per_char += 1
        
        # Stop bits
        bits_per_char += self.stopbits
        
        # Time = bits / (bits per second)
        char_time = bits_per_char / self.baudrate
        
        return char_time
    
    def _calculate_inter_frame_gap(self) -> float:
        """
        Calculate inter-frame gap per Modbus RTU specification
        
        Rules:
        - For baud rates ≤ 19200: 3.5 character times
        - For baud rates > 19200: Fixed 1.75ms
        
        Returns:
            Inter-frame gap in seconds
        """
        if self.baudrate > 19200:
            # Fixed value for high baud rates
            return 0.00175  # 1.75ms
        else:
            # 3.5 character times
            return self._char_time * 3.5
    
    @property
    def character_time(self) -> float:
        """Get character transmission time in seconds"""
        return self._char_time
    
    @property
    def inter_frame_gap(self) -> float:
        """Get inter-frame gap in seconds"""
        return self._inter_frame_gap
    
    @property
    def inter_frame_gap_ms(self) -> float:
        """Get inter-frame gap in milliseconds"""
        return self._inter_frame_gap * 1000
    
    @property
    def character_time_ms(self) -> float:
        """Get character time in milliseconds"""
        return self._char_time * 1000
    
    def get_response_timeout(self, request_size: int, max_response_size: int = 256,
                            processing_margin: float = 0.1) -> float:
        """
        Calculate reasonable timeout for receiving response
        
        Timeout includes:
        - Time for slave to receive request
        - Processing time (estimated)
        - Time for slave to send response
        - Safety margin
        
        Args:
            request_size: Size of request frame in bytes
            max_response_size: Maximum expected response size in bytes
            processing_margin: Additional processing time margin (seconds)
        
        Returns:
            Timeout in seconds
        """
        # Time to transmit request
        request_time = request_size * self._char_time
        
        # Time to transmit response
        response_time = max_response_size * self._char_time
        
        # Inter-frame gaps
        gaps = self._inter_frame_gap * 2
        
        # Total timeout
        timeout = request_time + response_time + gaps + processing_margin
        
        # Minimum timeout (avoid too-short timeouts)
        min_timeout = 0.1  # 100ms
        
        return max(timeout, min_timeout)
    
    def get_turnaround_delay(self) -> float:
        """
        Get turnaround delay for slave (time before sending response)
        
        Per Modbus spec, slave should wait at least 3.5 character times
        after receiving complete request before sending response
        
        Returns:
            Delay in seconds
        """
        return self._inter_frame_gap
    
    def validate_silent_interval(self, silence_duration: float) -> bool:
        """
        Check if silence duration is sufficient to indicate frame boundary
        
        Args:
            silence_duration: Duration of silence in seconds
        
        Returns:
            True if silence is sufficient (>= 3.5 char times)
        """
        return silence_duration >= self._inter_frame_gap
    
    def get_inter_byte_timeout(self) -> float:
        """
        Get timeout for receiving bytes within a frame
        
        Should be less than inter-frame gap but sufficient for byte transmission
        Typically 1.5 character times
        
        Returns:
            Timeout in seconds
        """
        return self._char_time * 1.5
    
    @staticmethod
    def estimate_frame_size(function_code: int, data_count: int = 0) -> int:
        """
        Estimate frame size for different function codes
        
        Args:
            function_code: Modbus function code
            data_count: Number of coils/registers being read/written
        
        Returns:
            Estimated frame size in bytes (including overhead)
        """
        # Base: slave_addr(1) + function(1) + CRC(2)
        base_size = 4
        
        # Function code specific estimates
        if function_code in [0x01, 0x02, 0x03, 0x04]:
            # Read functions: addr(2) + count(2)
            request_size = base_size + 4
            # Response: byte_count(1) + data
            if function_code in [0x01, 0x02]:  # Coils
                response_size = base_size + 1 + ((data_count + 7) // 8)
            else:  # Registers
                response_size = base_size + 1 + (data_count * 2)
            return max(request_size, response_size)
        
        elif function_code in [0x05, 0x06]:
            # Write single: addr(2) + value(2)
            return base_size + 4
        
        elif function_code == 0x0F:
            # Write multiple coils: addr(2) + count(2) + byte_count(1) + data
            return base_size + 5 + ((data_count + 7) // 8)
        
        elif function_code == 0x10:
            # Write multiple registers: addr(2) + count(2) + byte_count(1) + data
            return base_size + 5 + (data_count * 2)
        
        else:
            # Generic estimate
            return base_size + 32


def calculate_timeout_for_baudrate(baudrate: int, max_frame_size: int = 256) -> float:
    """
    Quick timeout calculation for a given baud rate
    
    Args:
        baudrate: Baud rate
        max_frame_size: Maximum expected frame size
    
    Returns:
        Recommended timeout in seconds
    """
    timing = ModbusRTUTiming(baudrate)
    return timing.get_response_timeout(max_frame_size, max_frame_size)


def get_recommended_baudrates() -> list:
    """
    Get list of recommended Modbus RTU baud rates
    
    Returns:
        List of tuples: (baudrate, description)
    """
    return [
        (1200, "1200 baud - Very slow, long cables"),
        (2400, "2400 baud - Slow, reliable"),
        (4800, "4800 baud - Standard low speed"),
        (9600, "9600 baud - Most common, default"),
        (19200, "19200 baud - Fast, standard"),
        (38400, "38400 baud - Very fast"),
        (57600, "57600 baud - High speed"),
        (115200, "115200 baud - Maximum standard speed"),
    ]
