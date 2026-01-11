import struct
from typing import List, Any, Optional
from src.models.device_models import ModbusDataType, ModbusEndianness

def encode_mapped_value(value: Any, 
                       data_type: ModbusDataType, 
                       endianness: ModbusEndianness = ModbusEndianness.BIG_ENDIAN,
                       scale: float = 1.0, 
                       offset: float = 0.0) -> List[int]:
    """Encodes a Python value into a list of 16-bit Modbus registers."""
    
    # 1. Apply scaling (reverse of decode)
    if isinstance(value, (int, float)) and data_type not in [ModbusDataType.BOOL, ModbusDataType.BIT, ModbusDataType.STRING]:
        value = (value - offset) / (scale if scale != 0 else 1.0)
    
    # 2. Convert to raw bytes based on type
    raw_bytes = b''
    
    if data_type in [ModbusDataType.INT16, ModbusDataType.UINT16, ModbusDataType.HEX16, ModbusDataType.BINARY16]:
        fmt = '>h' if data_type == ModbusDataType.INT16 else '>H'
        raw_bytes = struct.pack(fmt, int(value))
    
    elif data_type in [ModbusDataType.INT32, ModbusDataType.UINT32]:
        fmt = '>i' if data_type == ModbusDataType.INT32 else '>I'
        raw_bytes = struct.pack(fmt, int(value))
        
    elif data_type == ModbusDataType.FLOAT32:
        raw_bytes = struct.pack('>f', float(value))
        
    elif data_type in [ModbusDataType.INT64, ModbusDataType.UINT64]:
        fmt = '>q' if data_type == ModbusDataType.INT64 else '>Q'
        raw_bytes = struct.pack(fmt, int(value))

    elif data_type == ModbusDataType.FLOAT64:
        raw_bytes = struct.pack('>d', float(value))
        
    elif data_type == ModbusDataType.BOOL or data_type == ModbusDataType.BIT:
        raw_bytes = struct.pack('>H', 1 if value else 0)
        
    elif data_type == ModbusDataType.BCD16:
        s = f"{int(value):04d}"
        raw_bytes = bytes.fromhex(s)
        
    elif data_type == ModbusDataType.BCD32:
        s = f"{int(value):08d}"
        raw_bytes = bytes.fromhex(s)
        
    elif data_type == ModbusDataType.STRING:
        s = str(value).encode('ascii')
        if len(s) % 2 != 0:
            s += b'\x00'
        raw_bytes = s

    # 3. Apply endianness/swapping
    return _apply_swapping(raw_bytes, endianness)

def decode_mapped_value(registers: List[int], 
                       data_type: ModbusDataType, 
                       endianness: ModbusEndianness = ModbusEndianness.BIG_ENDIAN,
                       scale: float = 1.0, 
                       offset: float = 0.0) -> Any:
    """Decodes a list of 16-bit Modbus registers into a Python value."""
    if not registers:
        return None
        
    # 1. Reverse swapping to get Big-Endian bytes
    raw_bytes = _reverse_swapping(registers, data_type, endianness)
    
    # 2. Unpack based on type
    value = None
    try:
        if data_type == ModbusDataType.INT16:
            value = struct.unpack('>h', raw_bytes[:2])[0]
        elif data_type in [ModbusDataType.UINT16, ModbusDataType.HEX16, ModbusDataType.BINARY16]:
            value = struct.unpack('>H', raw_bytes[:2])[0]
        elif data_type == ModbusDataType.INT32:
            value = struct.unpack('>i', raw_bytes[:4])[0]
        elif data_type == ModbusDataType.UINT32:
            value = struct.unpack('>I', raw_bytes[:4])[0]
        elif data_type == ModbusDataType.FLOAT32:
            value = struct.unpack('>f', raw_bytes[:4])[0]
        elif data_type == ModbusDataType.INT64:
            value = struct.unpack('>q', raw_bytes[:8])[0]
        elif data_type == ModbusDataType.UINT64:
            value = struct.unpack('>Q', raw_bytes[:8])[0]
        elif data_type == ModbusDataType.FLOAT64:
            value = struct.unpack('>d', raw_bytes[:8])[0]
        elif data_type in [ModbusDataType.BOOL, ModbusDataType.BIT]:
            value = bool(struct.unpack('>H', raw_bytes[:2])[0])
        elif data_type == ModbusDataType.BCD16:
            value = int(raw_bytes[:2].hex())
        elif data_type == ModbusDataType.BCD32:
            value = int(raw_bytes[:4].hex())
        elif data_type == ModbusDataType.STRING:
            value = raw_bytes.decode('ascii').strip('\x00')
    except Exception:
        return None

    # 3. Apply scaling
    if isinstance(value, (int, float)) and data_type not in [ModbusDataType.BOOL, ModbusDataType.BIT, ModbusDataType.STRING, ModbusDataType.HEX16, ModbusDataType.BINARY16]:
        value = (value * scale) + offset
        
    # Special display formats
    if data_type == ModbusDataType.HEX16:
        return f"0x{value:04X}"
    if data_type == ModbusDataType.BINARY16:
        return f"0b{value:016b}"
        
    return value

def _apply_swapping(raw_bytes: bytes, endianness: ModbusEndianness) -> List[int]:
    """Converts big-endian bytes into 16-bit registers with requested swapping."""
    words = []
    for i in range(0, len(raw_bytes), 2):
        word = struct.unpack('>H', raw_bytes[i:i+2])[0]
        words.append(word)
        
    # Standard: ABCD -> [A, B, C, D] (where each is 16-bit word)
    # User's 4 cases:
    # 1. Big-endian (ABCD): AB CD ... 
    # 2. Little-endian (CDAB): Words reversed -> CD AB ...
    # 3. Big-endian byte swap (BADC): Bytes swapped within words -> BA DC ...
    # 4. Little-endian byte swap (DCBA): Word swap + byte swap -> DC BA ...
    
    if endianness in [ModbusEndianness.BIG_ENDIAN, ModbusEndianness.BIG_BIG]:
        return words
    
    if endianness in [ModbusEndianness.LITTLE_ENDIAN, ModbusEndianness.CDAB]:
        return words[::-1] # Word swap
        
    if endianness in [ModbusEndianness.BIG_ENDIAN_BYTE_SWAP, ModbusEndianness.BADC]:
        # Byte swap within each word
        return [((w & 0xFF) << 8) | ((w & 0xFF00) >> 8) for w in words]
        
    if endianness in [ModbusEndianness.LITTLE_ENDIAN_BYTE_SWAP, ModbusEndianness.LITTLE_LITTLE]:
        # Word swap AND Byte swap
        swapped_words = [((w & 0xFF) << 8) | ((w & 0xFF00) >> 8) for w in words]
        return swapped_words[::-1]
        
    return words

def _reverse_swapping(registers: List[int], data_type: ModbusDataType, endianness: ModbusEndianness) -> bytes:
    """Converts swapped registers back to big-endian bytes."""
    # Symmetrical operation
    swapped_words = _apply_swapping(struct.pack(f'>{len(registers)}H', *registers), endianness)
    return struct.pack(f'>{len(swapped_words)}H', *swapped_words)

def get_register_count(data_type: ModbusDataType, string_length: int = 0) -> int:
    """Returns number of 16-bit registers required for a data type."""
    counts = {
        ModbusDataType.INT16: 1, ModbusDataType.UINT16: 1,
        ModbusDataType.HEX16: 1, ModbusDataType.BINARY16: 1,
        ModbusDataType.INT32: 2, ModbusDataType.UINT32: 2,
        ModbusDataType.FLOAT32: 2,
        ModbusDataType.INT64: 4, ModbusDataType.UINT64: 4,
        ModbusDataType.FLOAT64: 4,
        ModbusDataType.BOOL: 1, ModbusDataType.BIT: 1,
        ModbusDataType.BCD16: 1, ModbusDataType.BCD32: 2,
    }
    if data_type == ModbusDataType.STRING:
        return (string_length + 1) // 2
    return counts.get(data_type, 1)
