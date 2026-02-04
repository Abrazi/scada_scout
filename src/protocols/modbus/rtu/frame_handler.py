"""
Modbus RTU Frame Handler
Handles frame parsing, construction, CRC validation, and all function codes
"""
import logging
import struct
from dataclasses import dataclass
from typing import Optional, List, Tuple
from enum import IntEnum

logger = logging.getLogger(__name__)


class ModbusFunctionCode(IntEnum):
    """Standard Modbus function codes"""
    READ_COILS = 0x01
    READ_DISCRETE_INPUTS = 0x02
    READ_HOLDING_REGISTERS = 0x03
    READ_INPUT_REGISTERS = 0x04
    WRITE_SINGLE_COIL = 0x05
    WRITE_SINGLE_REGISTER = 0x06
    READ_EXCEPTION_STATUS = 0x07
    DIAGNOSTICS = 0x08
    GET_COMM_EVENT_COUNTER = 0x0B
    WRITE_MULTIPLE_COILS = 0x0F
    WRITE_MULTIPLE_REGISTERS = 0x10


class ModbusExceptionCode(IntEnum):
    """Modbus exception codes"""
    ILLEGAL_FUNCTION = 0x01
    ILLEGAL_DATA_ADDRESS = 0x02
    ILLEGAL_DATA_VALUE = 0x03
    SLAVE_DEVICE_FAILURE = 0x04
    ACKNOWLEDGE = 0x05
    SLAVE_DEVICE_BUSY = 0x06
    MEMORY_PARITY_ERROR = 0x08
    GATEWAY_PATH_UNAVAILABLE = 0x0A
    GATEWAY_TARGET_DEVICE_FAILED = 0x0B


@dataclass
class ModbusRTUFrame:
    """Represents a complete Modbus RTU frame"""
    slave_address: int
    function_code: int
    data: bytes
    crc: int
    is_exception: bool = False
    exception_code: Optional[int] = None
    
    def __str__(self):
        if self.is_exception:
            return (f"RTU Frame [Slave={self.slave_address:02X}, "
                   f"Exception={self.function_code-0x80:02X}, "
                   f"Code={self.exception_code:02X}]")
        else:
            return (f"RTU Frame [Slave={self.slave_address:02X}, "
                   f"Func={self.function_code:02X}, "
                   f"Data={len(self.data)} bytes, CRC={self.crc:04X}]")


class ModbusRTUFrameHandler:
    """
    Handles Modbus RTU frame parsing, construction, and CRC validation
    """
    
    # Pre-computed CRC-16 lookup table for fast calculation
    _CRC_TABLE = [
        0x0000, 0xC0C1, 0xC181, 0x0140, 0xC301, 0x03C0, 0x0280, 0xC241,
        0xC601, 0x06C0, 0x0780, 0xC741, 0x0500, 0xC5C1, 0xC481, 0x0440,
        0xCC01, 0x0CC0, 0x0D80, 0xCD41, 0x0F00, 0xCFC1, 0xCE81, 0x0E40,
        0x0A00, 0xCAC1, 0xCB81, 0x0B40, 0xC901, 0x09C0, 0x0880, 0xC841,
        0xD801, 0x18C0, 0x1980, 0xD941, 0x1B00, 0xDBC1, 0xDA81, 0x1A40,
        0x1E00, 0xDEC1, 0xDF81, 0x1F40, 0xDD01, 0x1DC0, 0x1C80, 0xDC41,
        0x1400, 0xD4C1, 0xD581, 0x1540, 0xD701, 0x17C0, 0x1680, 0xD641,
        0xD201, 0x12C0, 0x1380, 0xD341, 0x1100, 0xD1C1, 0xD081, 0x1040,
        0xF001, 0x30C0, 0x3180, 0xF141, 0x3300, 0xF3C1, 0xF281, 0x3240,
        0x3600, 0xF6C1, 0xF781, 0x3740, 0xF501, 0x35C0, 0x3480, 0xF441,
        0x3C00, 0xFCC1, 0xFD81, 0x3D40, 0xFF01, 0x3FC0, 0x3E80, 0xFE41,
        0xFA01, 0x3AC0, 0x3B80, 0xFB41, 0x3900, 0xF9C1, 0xF881, 0x3840,
        0x2800, 0xE8C1, 0xE981, 0x2940, 0xEB01, 0x2BC0, 0x2A80, 0xEA41,
        0xEE01, 0x2EC0, 0x2F80, 0xEF41, 0x2D00, 0xEDC1, 0xEC81, 0x2C40,
        0xE401, 0x24C0, 0x2580, 0xE541, 0x2700, 0xE7C1, 0xE681, 0x2640,
        0x2200, 0xE2C1, 0xE381, 0x2340, 0xE101, 0x21C0, 0x2080, 0xE041,
        0xA001, 0x60C0, 0x6180, 0xA141, 0x6300, 0xA3C1, 0xA281, 0x6240,
        0x6600, 0xA6C1, 0xA781, 0x6740, 0xA501, 0x65C0, 0x6480, 0xA441,
        0x6C00, 0xACC1, 0xAD81, 0x6D40, 0xAF01, 0x6FC0, 0x6E80, 0xAE41,
        0xAA01, 0x6AC0, 0x6B80, 0xAB41, 0x6900, 0xA9C1, 0xA881, 0x6840,
        0x7800, 0xB8C1, 0xB981, 0x7940, 0xBB01, 0x7BC0, 0x7A80, 0xBA41,
        0xBE01, 0x7EC0, 0x7F80, 0xBF41, 0x7D00, 0xBDC1, 0xBC81, 0x7C40,
        0xB401, 0x74C0, 0x7580, 0xB541, 0x7700, 0xB7C1, 0xB681, 0x7640,
        0x7200, 0xB2C1, 0xB381, 0x7340, 0xB101, 0x71C0, 0x7080, 0xB041,
        0x5000, 0x90C1, 0x9181, 0x5140, 0x9301, 0x53C0, 0x5280, 0x9241,
        0x9601, 0x56C0, 0x5780, 0x9741, 0x5500, 0x95C1, 0x9481, 0x5440,
        0x9C01, 0x5CC0, 0x5D80, 0x9D41, 0x5F00, 0x9FC1, 0x9E81, 0x5E40,
        0x5A00, 0x9AC1, 0x9B81, 0x5B40, 0x9901, 0x59C0, 0x5880, 0x9841,
        0x8801, 0x48C0, 0x4980, 0x8941, 0x4B00, 0x8BC1, 0x8A81, 0x4A40,
        0x4E00, 0x8EC1, 0x8F81, 0x4F40, 0x8D01, 0x4DC0, 0x4C80, 0x8C41,
        0x4400, 0x84C1, 0x8581, 0x4540, 0x8701, 0x47C0, 0x4680, 0x8641,
        0x8201, 0x42C0, 0x4380, 0x8341, 0x4100, 0x81C1, 0x8081, 0x4040
    ]
    
    @classmethod
    def calculate_crc(cls, data: bytes) -> int:
        """
        Calculate CRC-16 (Modbus) for given data
        Uses pre-computed table for performance
        """
        crc = 0xFFFF
        for byte in data:
            index = (crc ^ byte) & 0xFF
            crc = (crc >> 8) ^ cls._CRC_TABLE[index]
        return crc
    
    @classmethod
    def validate_crc(cls, frame: bytes) -> bool:
        """
        Validate CRC of a complete frame
        Frame must include CRC bytes at the end
        """
        if len(frame) < 4:  # Minimum: addr + func + crc(2)
            return False
        
        # Extract data and CRC
        data = frame[:-2]
        received_crc = struct.unpack('<H', frame[-2:])[0]  # Little-endian
        
        # Calculate expected CRC
        calculated_crc = cls.calculate_crc(data)
        
        is_valid = received_crc == calculated_crc
        if not is_valid:
            logger.warning(f"CRC mismatch: received={received_crc:04X}, "
                          f"calculated={calculated_crc:04X}")
        
        return is_valid
    
    @classmethod
    def parse_frame(cls, frame_bytes: bytes) -> Optional[ModbusRTUFrame]:
        """
        Parse a complete RTU frame
        Returns ModbusRTUFrame or None if invalid
        """
        if len(frame_bytes) < 4:
            logger.error(f"Frame too short: {len(frame_bytes)} bytes")
            return None
        
        # Validate CRC first
        if not cls.validate_crc(frame_bytes):
            logger.error("CRC validation failed - frame discarded")
            return None
        
        # Extract fields
        slave_address = frame_bytes[0]
        function_code = frame_bytes[1]
        data = frame_bytes[2:-2]  # Everything except addr, func, and CRC
        crc = struct.unpack('<H', frame_bytes[-2:])[0]
        
        # Check if this is an exception response
        is_exception = (function_code & 0x80) != 0
        exception_code = None
        
        if is_exception:
            if len(data) >= 1:
                exception_code = data[0]
            logger.debug(f"Exception response: func={function_code-0x80:02X}, "
                        f"exception={exception_code:02X}")
        
        return ModbusRTUFrame(
            slave_address=slave_address,
            function_code=function_code,
            data=data,
            crc=crc,
            is_exception=is_exception,
            exception_code=exception_code
        )
    
    @classmethod
    def build_frame(cls, slave_address: int, function_code: int, 
                    data: bytes = b'') -> bytes:
        """
        Build a complete RTU frame with CRC
        """
        # Validate inputs
        if not 0 <= slave_address <= 247:
            raise ValueError(f"Invalid slave address: {slave_address}")
        
        if not 1 <= function_code <= 127:
            raise ValueError(f"Invalid function code: {function_code}")
        
        # Build frame without CRC
        frame = bytes([slave_address, function_code]) + data
        
        # Calculate and append CRC (little-endian)
        crc = cls.calculate_crc(frame)
        frame += struct.pack('<H', crc)
        
        return frame
    
    @classmethod
    def build_exception_response(cls, slave_address: int, function_code: int,
                                 exception_code: int) -> bytes:
        """Build an exception response frame"""
        # Exception response: set high bit of function code
        exception_func = function_code | 0x80
        data = bytes([exception_code])
        
        return cls.build_frame(slave_address, exception_func, data)
    
    # ========================================================================
    # Function Code Implementations - Request Builders
    # ========================================================================
    
    @classmethod
    def build_read_coils_request(cls, slave_address: int, start_address: int,
                                count: int) -> bytes:
        """FC01: Read Coils"""
        if not 1 <= count <= 2000:
            raise ValueError(f"Invalid coil count: {count}")
        
        data = struct.pack('>HH', start_address, count)
        return cls.build_frame(slave_address, ModbusFunctionCode.READ_COILS, data)
    
    @classmethod
    def build_read_discrete_inputs_request(cls, slave_address: int, 
                                          start_address: int, count: int) -> bytes:
        """FC02: Read Discrete Inputs"""
        if not 1 <= count <= 2000:
            raise ValueError(f"Invalid discrete input count: {count}")
        
        data = struct.pack('>HH', start_address, count)
        return cls.build_frame(slave_address, ModbusFunctionCode.READ_DISCRETE_INPUTS, data)
    
    @classmethod
    def build_read_holding_registers_request(cls, slave_address: int,
                                            start_address: int, count: int) -> bytes:
        """FC03: Read Holding Registers"""
        if not 1 <= count <= 125:
            raise ValueError(f"Invalid register count: {count}")
        
        data = struct.pack('>HH', start_address, count)
        return cls.build_frame(slave_address, ModbusFunctionCode.READ_HOLDING_REGISTERS, data)
    
    @classmethod
    def build_read_input_registers_request(cls, slave_address: int,
                                          start_address: int, count: int) -> bytes:
        """FC04: Read Input Registers"""
        if not 1 <= count <= 125:
            raise ValueError(f"Invalid register count: {count}")
        
        data = struct.pack('>HH', start_address, count)
        return cls.build_frame(slave_address, ModbusFunctionCode.READ_INPUT_REGISTERS, data)
    
    @classmethod
    def build_write_single_coil_request(cls, slave_address: int, address: int,
                                       value: bool) -> bytes:
        """FC05: Write Single Coil"""
        # Coil value: 0xFF00 for ON, 0x0000 for OFF
        coil_value = 0xFF00 if value else 0x0000
        data = struct.pack('>HH', address, coil_value)
        return cls.build_frame(slave_address, ModbusFunctionCode.WRITE_SINGLE_COIL, data)
    
    @classmethod
    def build_write_single_register_request(cls, slave_address: int, address: int,
                                           value: int) -> bytes:
        """FC06: Write Single Register"""
        if not 0 <= value <= 0xFFFF:
            raise ValueError(f"Invalid register value: {value}")
        
        data = struct.pack('>HH', address, value)
        return cls.build_frame(slave_address, ModbusFunctionCode.WRITE_SINGLE_REGISTER, data)
    
    @classmethod
    def build_read_exception_status_request(cls, slave_address: int) -> bytes:
        """FC07: Read Exception Status (8 coils)"""
        return cls.build_frame(slave_address, ModbusFunctionCode.READ_EXCEPTION_STATUS)
    
    @classmethod
    def build_diagnostics_request(cls, slave_address: int, sub_function: int,
                                  data: bytes = b'\x00\x00') -> bytes:
        """FC08: Diagnostics"""
        request_data = struct.pack('>H', sub_function) + data
        return cls.build_frame(slave_address, ModbusFunctionCode.DIAGNOSTICS, request_data)
    
    @classmethod
    def build_get_comm_event_counter_request(cls, slave_address: int) -> bytes:
        """FC11: Get Comm Event Counter"""
        return cls.build_frame(slave_address, ModbusFunctionCode.GET_COMM_EVENT_COUNTER)
    
    @classmethod
    def build_write_multiple_coils_request(cls, slave_address: int, start_address: int,
                                          values: List[bool]) -> bytes:
        """FC15: Write Multiple Coils"""
        count = len(values)
        if not 1 <= count <= 1968:
            raise ValueError(f"Invalid coil count: {count}")
        
        # Pack coils into bytes (8 coils per byte)
        byte_count = (count + 7) // 8
        coil_bytes = bytearray(byte_count)
        
        for i, value in enumerate(values):
            if value:
                byte_index = i // 8
                bit_index = i % 8
                coil_bytes[byte_index] |= (1 << bit_index)
        
        data = struct.pack('>HHB', start_address, count, byte_count) + bytes(coil_bytes)
        return cls.build_frame(slave_address, ModbusFunctionCode.WRITE_MULTIPLE_COILS, data)
    
    @classmethod
    def build_write_multiple_registers_request(cls, slave_address: int, start_address: int,
                                              values: List[int]) -> bytes:
        """FC16: Write Multiple Registers"""
        count = len(values)
        if not 1 <= count <= 123:
            raise ValueError(f"Invalid register count: {count}")
        
        # Validate all values
        for value in values:
            if not 0 <= value <= 0xFFFF:
                raise ValueError(f"Invalid register value: {value}")
        
        byte_count = count * 2
        data = struct.pack('>HHB', start_address, count, byte_count)
        
        # Pack register values (big-endian)
        for value in values:
            data += struct.pack('>H', value)
        
        return cls.build_frame(slave_address, ModbusFunctionCode.WRITE_MULTIPLE_REGISTERS, data)
    
    # ========================================================================
    # Response Parsers
    # ========================================================================
    
    @classmethod
    def parse_read_coils_response(cls, frame: ModbusRTUFrame) -> Optional[List[bool]]:
        """Parse FC01/FC02 response"""
        if frame.is_exception:
            return None
        
        if len(frame.data) < 1:
            logger.error("Invalid read coils response: no byte count")
            return None
        
        byte_count = frame.data[0]
        coil_bytes = frame.data[1:1+byte_count]
        
        if len(coil_bytes) != byte_count:
            logger.error("Invalid read coils response: byte count mismatch")
            return None
        
        # Unpack coils from bytes
        coils = []
        for byte in coil_bytes:
            for bit in range(8):
                coils.append((byte & (1 << bit)) != 0)
        
        return coils
    
    @classmethod
    def parse_read_registers_response(cls, frame: ModbusRTUFrame) -> Optional[List[int]]:
        """Parse FC03/FC04 response"""
        if frame.is_exception:
            return None
        
        if len(frame.data) < 1:
            logger.error("Invalid read registers response: no byte count")
            return None
        
        byte_count = frame.data[0]
        register_bytes = frame.data[1:1+byte_count]
        
        if len(register_bytes) != byte_count or byte_count % 2 != 0:
            logger.error("Invalid read registers response: byte count mismatch")
            return None
        
        # Unpack registers (big-endian)
        register_count = byte_count // 2
        registers = []
        for i in range(register_count):
            offset = i * 2
            value = struct.unpack('>H', register_bytes[offset:offset+2])[0]
            registers.append(value)
        
        return registers
    
    @classmethod
    def parse_write_single_response(cls, frame: ModbusRTUFrame) -> Optional[Tuple[int, int]]:
        """Parse FC05/FC06 response - returns (address, value)"""
        if frame.is_exception:
            return None
        
        if len(frame.data) != 4:
            logger.error("Invalid write single response: wrong data length")
            return None
        
        address, value = struct.unpack('>HH', frame.data)
        return (address, value)
    
    @classmethod
    def parse_write_multiple_response(cls, frame: ModbusRTUFrame) -> Optional[Tuple[int, int]]:
        """Parse FC15/FC16 response - returns (start_address, count)"""
        if frame.is_exception:
            return None
        
        if len(frame.data) != 4:
            logger.error("Invalid write multiple response: wrong data length")
            return None
        
        start_address, count = struct.unpack('>HH', frame.data)
        return (start_address, count)
    
    @classmethod
    def parse_read_exception_status_response(cls, frame: ModbusRTUFrame) -> Optional[int]:
        """Parse FC07 response - returns status byte"""
        if frame.is_exception:
            return None
        
        if len(frame.data) != 1:
            logger.error("Invalid exception status response: wrong data length")
            return None
        
        return frame.data[0]
    
    @classmethod
    def parse_get_comm_event_counter_response(cls, frame: ModbusRTUFrame) -> Optional[Tuple[int, int]]:
        """Parse FC11 response - returns (status, event_count)"""
        if frame.is_exception:
            return None
        
        if len(frame.data) != 4:
            logger.error("Invalid comm event counter response: wrong data length")
            return None
        
        status, event_count = struct.unpack('>HH', frame.data)
        return (status, event_count)
    
    # ========================================================================
    # Response Builders (for Slave)
    # ========================================================================
    
    @classmethod
    def build_read_coils_response(cls, slave_address: int, coils: List[bool]) -> bytes:
        """Build FC01/FC02 response"""
        byte_count = (len(coils) + 7) // 8
        coil_bytes = bytearray(byte_count)
        
        for i, value in enumerate(coils):
            if value:
                byte_index = i // 8
                bit_index = i % 8
                coil_bytes[byte_index] |= (1 << bit_index)
        
        data = bytes([byte_count]) + bytes(coil_bytes)
        return cls.build_frame(slave_address, ModbusFunctionCode.READ_COILS, data)
    
    @classmethod
    def build_read_registers_response(cls, slave_address: int, function_code: int,
                                     registers: List[int]) -> bytes:
        """Build FC03/FC04 response"""
        byte_count = len(registers) * 2
        data = bytes([byte_count])
        
        for value in registers:
            data += struct.pack('>H', value)
        
        return cls.build_frame(slave_address, function_code, data)
    
    @classmethod
    def build_write_single_response(cls, slave_address: int, function_code: int,
                                   address: int, value: int) -> bytes:
        """Build FC05/FC06 response (echo request)"""
        data = struct.pack('>HH', address, value)
        return cls.build_frame(slave_address, function_code, data)
    
    @classmethod
    def build_write_multiple_response(cls, slave_address: int, function_code: int,
                                     start_address: int, count: int) -> bytes:
        """Build FC15/FC16 response"""
        data = struct.pack('>HH', start_address, count)
        return cls.build_frame(slave_address, function_code, data)
