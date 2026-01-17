"""
IEC 61850 Ctypes Wrapper for Python

This module provides a simplified, high-level Python interface to libiec61850 using ctypes.
It works cross-platform (Windows/Linux/macOS) without requiring SWIG or pyiec61850.

Usage:
    import iec61850_wrapper as iec61850
    
    # Create connection
    con = iec61850.IedConnection_create()
    error = iec61850.IedConnection_connect(con, "192.168.1.10", 102)
    
    if error == iec61850.IED_ERROR_OK:
        # Read value
        value, error = iec61850.IedConnection_readFloatValue(con, "LD0/MMXU1.TotW.mag.f", iec61850.IEC61850_FC_MX)
        
        # Close connection
        iec61850.IedConnection_close(con)
    
    iec61850.IedConnection_destroy(con)
"""

import ctypes
import sys
import os
import platform
from ctypes import (
    POINTER, c_void_p, c_char_p, c_int, c_uint, c_bool, c_float, c_double,
    c_int32, c_int64, c_uint8, c_uint16, c_uint32, c_uint64, Structure
)

# ============================================================================
# Library Loading (Cross-Platform)
# ============================================================================

def _find_library():
    """
    Find and load the libiec61850 library cross-platform.
    
    Search order:
    1. Current directory
    2. Project lib directory
    3. System library paths
    """
    system = platform.system()
    
    # Library names by platform
    if system == "Windows":
        lib_names = ["iec61850.dll", "libiec61850.dll"]
    elif system == "Darwin":  # macOS
        lib_names = ["libiec61850.dylib", "iec61850.dylib"]
    else:  # Linux and others
        lib_names = ["libiec61850.so", "libiec61850.so.1"]
    
    # Paths to search
    search_paths = [
        os.path.dirname(__file__),  # Same directory as this file
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "lib"),  # Project lib dir
        os.getcwd(),  # Current working directory
    ]
    
    # Try each combination of path and library name
    for path in search_paths:
        for lib_name in lib_names:
            lib_path = os.path.join(path, lib_name)
            if os.path.exists(lib_path):
                try:
                    return ctypes.CDLL(lib_path)
                except Exception as e:
                    pass  # Try next option
    
    # Try system library search
    for lib_name in lib_names:
        try:
            return ctypes.CDLL(lib_name)
        except Exception:
            pass
    
    # Library not found
    raise RuntimeError(
        f"Cannot find libiec61850 library. Searched for: {lib_names}\n"
        f"Please ensure libiec61850 is compiled and available in:\n"
        f"  - System library path (PATH on Windows, LD_LIBRARY_PATH on Linux)\n"
        f"  - Current directory\n"
        f"  - {os.path.join(os.path.dirname(__file__), 'lib')}"
    )

try:
    _lib = _find_library()
    HAS_LIBIEC61850 = True
except RuntimeError as e:
    _lib = None
    HAS_LIBIEC61850 = False
    _LOAD_ERROR = str(e)

# ============================================================================
# Type Definitions
# ============================================================================

# Opaque pointers (implementation hidden in C library)
IedConnection = c_void_p
MmsValue = c_void_p
LinkedList = c_void_p
ControlObjectClient = c_void_p

# ============================================================================
# Error Codes
# ============================================================================

# IedClientError enum
IED_ERROR_OK = 0
IED_ERROR_NOT_CONNECTED = 1
IED_ERROR_ALREADY_CONNECTED = 2
IED_ERROR_CONNECTION_LOST = 3
IED_ERROR_SERVICE_NOT_SUPPORTED = 4
IED_ERROR_CONNECTION_REJECTED = 5
IED_ERROR_OUTSTANDING_CALL_LIMIT_REACHED = 6
IED_ERROR_USER_PROVIDED_INVALID_ARGUMENT = 7
IED_ERROR_ENABLE_REPORT_FAILED_DATASET_MISMATCH = 8
IED_ERROR_OBJECT_REFERENCE_INVALID = 10
IED_ERROR_UNEXPECTED_VALUE_RECEIVED = 11
IED_ERROR_TIMEOUT = 12
IED_ERROR_OBJECT_ACCESS_DENIED = 13
IED_ERROR_OBJECT_UNDEFINED = 14
IED_ERROR_INVALID_ADDRESS = 15
IED_ERROR_HARDWARE_FAULT = 16
IED_ERROR_TYPE_INCONSISTENT = 17
IED_ERROR_TEMPORARILY_UNAVAILABLE = 18
IED_ERROR_OBJECT_VALUE_INVALID = 19
IED_ERROR_OPTION_NOT_SUPPORTED = 20
IED_ERROR_UNKNOWN = 99

# IedConnectionState enum
IED_STATE_CLOSED = 0
IED_STATE_CONNECTING = 1
IED_STATE_CONNECTED = 2
IED_STATE_CLOSING = 3

# Functional Constraints
IEC61850_FC_ST = 0  # Status
IEC61850_FC_MX = 1  # Measurands
IEC61850_FC_SP = 2  # Setpoint
IEC61850_FC_SV = 3  # Substitution
IEC61850_FC_CF = 4  # Configuration
IEC61850_FC_DC = 5  # Description
IEC61850_FC_SG = 6  # Setting group
IEC61850_FC_SE = 7  # Setting group editable
IEC61850_FC_SR = 8  # Service response
IEC61850_FC_OR = 9  # Oper received
IEC61850_FC_BL = 10 # Blocking
IEC61850_FC_EX = 11 # Extended definition
IEC61850_FC_CO = 12 # Control
IEC61850_FC_US = 13 # Unicast SV
IEC61850_FC_MS = 14 # Multicast SV
IEC61850_FC_RP = 15 # Report
IEC61850_FC_BR = 16 # Buffered report
IEC61850_FC_LG = 17 # Log
IEC61850_FC_GO = 18 # GOOSE
IEC61850_FC_ALL = 99
IEC61850_FC_NONE = -1

# MMS Types
MMS_ARRAY = 0
MMS_STRUCTURE = 1
MMS_BOOLEAN = 2
MMS_BIT_STRING = 3
MMS_INTEGER = 4
MMS_UNSIGNED = 5
MMS_FLOAT = 6
MMS_OCTET_STRING = 7
MMS_VISIBLE_STRING = 8
MMS_GENERALIZED_TIME = 9
MMS_BINARY_TIME = 10
MMS_BCD = 11
MMS_OBJ_ID = 12
MMS_STRING = 13
MMS_UTC_TIME = 14
MMS_DATA_ACCESS_ERROR = 15

# ACSI Classes (for browsing)
ACSI_CLASS_DATA_OBJECT = 0
ACSI_CLASS_DATA_SET = 1
ACSI_CLASS_BRCB = 2
ACSI_CLASS_URCB = 3
ACSI_CLASS_LCB = 4
ACSI_CLASS_LOG = 5
ACSI_CLASS_SGCB = 6
ACSI_CLASS_GoCB = 7
ACSI_CLASS_GsCB = 8
ACSI_CLASS_MSVCB = 9
ACSI_CLASS_USVCB = 10

# ============================================================================
# Helper Functions
# ============================================================================

def _check_lib():
    """Check if library is loaded, raise exception if not."""
    if not HAS_LIBIEC61850:
        raise RuntimeError(_LOAD_ERROR)

def _encode_str(s):
    """Convert Python string to bytes for C functions."""
    if s is None:
        return None
    if isinstance(s, bytes):
        return s
    return s.encode('utf-8')

def _decode_str(b):
    """Convert C string (bytes) to Python string."""
    if b is None:
        return None
    if isinstance(b, str):
        return b
    return b.decode('utf-8', errors='replace')

# ============================================================================
# Connection Management
# ============================================================================

def IedConnection_create():
    """
    Create a new IedConnection instance.
    
    Returns:
        IedConnection: Connection handle (must be destroyed with IedConnection_destroy)
    """
    _check_lib()
    func = _lib.IedConnection_create
    func.restype = IedConnection
    func.argtypes = []
    return func()

def IedConnection_destroy(connection):
    """
    Destroy an IedConnection and free resources.
    
    Args:
        connection: IedConnection handle
    """
    _check_lib()
    func = _lib.IedConnection_destroy
    func.restype = None
    func.argtypes = [IedConnection]
    func(connection)

def IedConnection_connect(connection, hostname, tcp_port):
    """
    Connect to an IED server.
    
    Args:
        connection: IedConnection handle
        hostname: IP address or hostname (string)
        tcp_port: TCP port number (int)
    
    Returns:
        int: Error code (IED_ERROR_OK on success)
    """
    _check_lib()
    func = _lib.IedConnection_connect
    func.restype = None  # void return type
    func.argtypes = [IedConnection, POINTER(c_int), c_char_p, c_int]
    
    error = c_int()
    func(connection, ctypes.byref(error), _encode_str(hostname), tcp_port)
    return error.value

def IedConnection_close(connection):
    """
    Close the connection to the IED server.
    
    Args:
        connection: IedConnection handle
    """
    _check_lib()
    func = _lib.IedConnection_close
    func.restype = None
    func.argtypes = [IedConnection]
    func(connection)

def IedConnection_getState(connection):
    """
    Get the current connection state.
    
    Args:
        connection: IedConnection handle
    
    Returns:
        int: Connection state (IED_STATE_CONNECTED, etc.)
    """
    _check_lib()
    func = _lib.IedConnection_getState
    func.restype = c_int
    func.argtypes = [IedConnection]
    return func(connection)

# ============================================================================
# Device Browsing
# ============================================================================

def IedConnection_getLogicalDeviceList(connection):
    """
    Get list of logical devices from the IED.
    
    Args:
        connection: IedConnection handle
    
    Returns:
        tuple: (LinkedList, error_code)
    """
    _check_lib()
    func = _lib.IedConnection_getLogicalDeviceList
    func.restype = LinkedList
    func.argtypes = [IedConnection, POINTER(c_int)]
    
    error = c_int()
    result = func(connection, ctypes.byref(error))
    return (result, error.value)

def IedConnection_getLogicalDeviceDirectory(connection, logical_device_name):
    """
    Get directory of logical nodes for a logical device.
    
    Args:
        connection: IedConnection handle
        logical_device_name: Name of the logical device (string)
    
    Returns:
        tuple: (LinkedList, error_code)
    """
    _check_lib()
    func = _lib.IedConnection_getLogicalDeviceDirectory
    func.restype = LinkedList
    func.argtypes = [IedConnection, POINTER(c_int), c_char_p]
    
    error = c_int()
    result = func(connection, ctypes.byref(error), _encode_str(logical_device_name))
    return (result, error.value)

def IedConnection_getLogicalNodeDirectory(connection, logical_node_reference, acsi_class):
    """
    Get directory of data objects within a logical node.
    
    Args:
        connection: IedConnection handle
        logical_node_reference: Full reference (e.g., "LD0/MMXU1")
        acsi_class: ACSI class filter (ACSI_CLASS_DATA_OBJECT, etc.)
    
    Returns:
        tuple: (LinkedList, error_code)
    """
    _check_lib()
    func = _lib.IedConnection_getLogicalNodeDirectory
    func.restype = LinkedList
    func.argtypes = [IedConnection, POINTER(c_int), c_char_p, c_int]
    
    error = c_int()
    result = func(connection, ctypes.byref(error), _encode_str(logical_node_reference), acsi_class)
    return (result, error.value)

def IedConnection_getDataDirectory(connection, data_reference):
    """
    Get directory of data attributes.
    
    Args:
        connection: IedConnection handle
        data_reference: Data object reference
    
    Returns:
        tuple: (LinkedList, error_code)
    """
    _check_lib()
    func = _lib.IedConnection_getDataDirectory
    func.restype = LinkedList
    func.argtypes = [IedConnection, POINTER(c_int), c_char_p]
    
    error = c_int()
    result = func(connection, ctypes.byref(error), _encode_str(data_reference))
    return (result, error.value)

def IedConnection_getDataDirectoryByFC(connection, data_reference, fc):
    """
    Get directory of data attributes filtered by functional constraint.
    
    Args:
        connection: IedConnection handle
        data_reference: Data object reference
        fc: Functional constraint (IEC61850_FC_ST, etc.)
    
    Returns:
        tuple: (LinkedList, error_code)
    """
    _check_lib()
    func = _lib.IedConnection_getDataDirectoryByFC
    func.restype = LinkedList
    func.argtypes = [IedConnection, POINTER(c_int), c_char_p, c_int]
    
    error = c_int()
    result = func(connection, ctypes.byref(error), _encode_str(data_reference), fc)
    return (result, error.value)

def IedConnection_getDataSetDirectory(connection, dataset_reference):
    """
    Get directory of DataSet entries (FCDA references).
    
    Args:
        connection: IedConnection handle
        dataset_reference: Full DataSet reference (e.g., "LD0/LLN0$ds1")
    
    Returns:
        tuple: (LinkedList, error_code, is_deletable)
    """
    _check_lib()
    func = _lib.IedConnection_getDataSetDirectory
    func.restype = LinkedList
    func.argtypes = [IedConnection, POINTER(c_int), c_char_p, POINTER(c_bool)]

    error = c_int()
    deletable = c_bool()
    result = func(connection, ctypes.byref(error), _encode_str(dataset_reference), ctypes.byref(deletable))
    return (result, error.value, bool(deletable.value))

# ============================================================================
# Reading Data
# ============================================================================

def IedConnection_readObject(connection, object_reference, fc):
    """
    Read a data object as MmsValue.
    
    Args:
        connection: IedConnection handle
        object_reference: Full object reference
        fc: Functional constraint
    
    Returns:
        tuple: (MmsValue, error_code)
    """
    _check_lib()
    func = _lib.IedConnection_readObject
    func.restype = MmsValue
    func.argtypes = [IedConnection, POINTER(c_int), c_char_p, c_int]
    
    error = c_int()
    result = func(connection, ctypes.byref(error), _encode_str(object_reference), fc)
    return (result, error.value)

def IedConnection_readBooleanValue(connection, object_reference, fc):
    """
    Read a boolean value.
    
    Args:
        connection: IedConnection handle
        object_reference: Full object reference
        fc: Functional constraint
    
    Returns:
        tuple: (bool, error_code)
    """
    _check_lib()
    func = _lib.IedConnection_readBooleanValue
    func.restype = c_bool
    func.argtypes = [IedConnection, POINTER(c_int), c_char_p, c_int]
    
    error = c_int()
    result = func(connection, ctypes.byref(error), _encode_str(object_reference), fc)
    return (bool(result), error.value)

def IedConnection_readFloatValue(connection, object_reference, fc):
    """
    Read a float value.
    
    Args:
        connection: IedConnection handle
        object_reference: Full object reference
        fc: Functional constraint
    
    Returns:
        tuple: (float, error_code)
    """
    _check_lib()
    func = _lib.IedConnection_readFloatValue
    func.restype = c_float
    func.argtypes = [IedConnection, POINTER(c_int), c_char_p, c_int]
    
    error = c_int()
    result = func(connection, ctypes.byref(error), _encode_str(object_reference), fc)
    return (float(result), error.value)

def IedConnection_readInt32Value(connection, object_reference, fc):
    """
    Read an int32 value.
    
    Args:
        connection: IedConnection handle
        object_reference: Full object reference
        fc: Functional constraint
    
    Returns:
        tuple: (int, error_code)
    """
    _check_lib()
    func = _lib.IedConnection_readInt32Value
    func.restype = c_int32
    func.argtypes = [IedConnection, POINTER(c_int), c_char_p, c_int]
    
    error = c_int()
    result = func(connection, ctypes.byref(error), _encode_str(object_reference), fc)
    return (int(result), error.value)

def IedConnection_readInt64Value(connection, object_reference, fc):
    """
    Read an int64 value.
    
    Args:
        connection: IedConnection handle
        object_reference: Full object reference
        fc: Functional constraint
    
    Returns:
        tuple: (int, error_code)
    """
    _check_lib()
    func = _lib.IedConnection_readInt64Value
    func.restype = c_int64
    func.argtypes = [IedConnection, POINTER(c_int), c_char_p, c_int]
    
    error = c_int()
    result = func(connection, ctypes.byref(error), _encode_str(object_reference), fc)
    return (int(result), error.value)

def IedConnection_readUnsigned32Value(connection, object_reference, fc):
    """
    Read an unsigned 32-bit value.
    
    Args:
        connection: IedConnection handle
        object_reference: Full object reference
        fc: Functional constraint
    
    Returns:
        tuple: (int, error_code)
    """
    _check_lib()
    func = _lib.IedConnection_readUnsigned32Value
    func.restype = c_uint32
    func.argtypes = [IedConnection, POINTER(c_int), c_char_p, c_int]
    
    error = c_int()
    result = func(connection, ctypes.byref(error), _encode_str(object_reference), fc)
    return (int(result), error.value)

def IedConnection_readStringValue(connection, object_reference, fc):
    """
    Read a string value.
    
    Args:
        connection: IedConnection handle
        object_reference: Full object reference
        fc: Functional constraint
    
    Returns:
        tuple: (str, error_code)
    """
    _check_lib()
    func = _lib.IedConnection_readStringValue
    func.restype = c_char_p
    func.argtypes = [IedConnection, POINTER(c_int), c_char_p, c_int]
    
    error = c_int()
    result = func(connection, ctypes.byref(error), _encode_str(object_reference), fc)
    return (_decode_str(result), error.value)

def IedConnection_readBitStringValue(connection, object_reference, fc):
    """
    Read a bit string value.
    
    Args:
        connection: IedConnection handle
        object_reference: Full object reference
        fc: Functional constraint
    
    Returns:
        tuple: (int, error_code) - bit string as integer
    """
    _check_lib()
    func = _lib.IedConnection_readBitStringValue
    func.restype = c_uint32
    func.argtypes = [IedConnection, POINTER(c_int), c_char_p, c_int]
    
    error = c_int()
    result = func(connection, ctypes.byref(error), _encode_str(object_reference), fc)
    return (int(result), error.value)

# ============================================================================
# Writing Data
# ============================================================================

def IedConnection_writeObject(connection, object_reference, fc, value):
    """
    Write a data object.
    
    Args:
        connection: IedConnection handle
        object_reference: Full object reference
        fc: Functional constraint
        value: MmsValue to write
    
    Returns:
        int: Error code
    """
    if not connection:
        return IED_ERROR_NOT_CONNECTED
    if not value:
        logger.error(f"IedConnection_writeObject: Attempted to write NULL MmsValue to {object_reference}")
        return IED_ERROR_USER_PROVIDED_INVALID_ARGUMENT
        
    _check_lib()
    func = _lib.IedConnection_writeObject
    func.restype = None  # C function returns void
    func.argtypes = [IedConnection, POINTER(c_int), c_char_p, c_int, MmsValue]
    
    error = c_int()
    func(connection, ctypes.byref(error), _encode_str(object_reference), fc, value)
    return error.value

def IedConnection_writeBooleanValue(connection, object_reference, fc, value):
    """
    Write a boolean value.
    
    Args:
        connection: IedConnection handle
        object_reference: Full object reference
        fc: Functional constraint
        value: Boolean value
    
    Returns:
        int: Error code
    """
    _check_lib()
    func = _lib.IedConnection_writeBooleanValue
    func.restype = None
    func.argtypes = [IedConnection, POINTER(c_int), c_char_p, c_int, c_bool]
    
    error = c_int()
    func(connection, ctypes.byref(error), _encode_str(object_reference), fc, bool(value))
    return error.value

def IedConnection_writeFloatValue(connection, object_reference, fc, value):
    """
    Write a float value.
    
    Args:
        connection: IedConnection handle
        object_reference: Full object reference
        fc: Functional constraint
        value: Float value
    
    Returns:
        int: Error code
    """
    _check_lib()
    func = _lib.IedConnection_writeFloatValue
    func.restype = None
    func.argtypes = [IedConnection, POINTER(c_int), c_char_p, c_int, c_float]
    
    error = c_int()
    func(connection, ctypes.byref(error), _encode_str(object_reference), fc, float(value))
    return error.value

def IedConnection_writeInt32Value(connection, object_reference, fc, value):
    """
    Write an int32 value.
    
    Args:
        connection: IedConnection handle
        object_reference: Full object reference
        fc: Functional constraint
        value: Integer value
    
    Returns:
        int: Error code
    """
    _check_lib()
    func = _lib.IedConnection_writeInt32Value
    func.restype = None
    func.argtypes = [IedConnection, POINTER(c_int), c_char_p, c_int, c_int32]
    
    error = c_int()
    func(connection, ctypes.byref(error), _encode_str(object_reference), fc, int(value))
    return error.value

# ============================================================================
# Control Model Functions (ControlObjectClient)
# ============================================================================

def ControlObjectClient_create(object_reference, connection):
    """
    Create a ControlObjectClient instance for easy control operations.
    
    Args:
        object_reference: Full reference to the control object (e.g. "SimpleIO/GGIO1.SPCSO1")
        connection: Active IedConnection handle
    
    Returns:
        ControlObjectClient: Handle
    """
    _check_lib()
    func = _lib.ControlObjectClient_create
    func.restype = ControlObjectClient
    func.argtypes = [c_char_p, IedConnection]
    return func(_encode_str(object_reference), connection)

def ControlObjectClient_destroy(client):
    """
    Destroy ControlObjectClient instance.
    
    Args:
        client: ControlObjectClient handle
    """
    _check_lib()
    func = _lib.ControlObjectClient_destroy
    func.restype = None
    func.argtypes = [ControlObjectClient]
    func(client)

def ControlObjectClient_getControlModel(client):
    """
    Get the control model of the control object.
    
    Args:
        client: ControlObjectClient handle
        
    Returns:
        int: Control model (0=STATUS_ONLY, 1=DIRECT_NORMAL, 2=SBO_NORMAL, 3=DIRECT_ENHANCED, 4=SBO_ENHANCED)
    """
    _check_lib()
    func = _lib.ControlObjectClient_getControlModel
    func.restype = c_int
    func.argtypes = [ControlObjectClient]
    return func(client)

def ControlObjectClient_getLastError(client):
    """
    Get the last error code from the control object.
    
    Args:
        client: ControlObjectClient handle
        
    Returns:
        int: Last IedClientError code
    """
    _check_lib()
    func = _lib.ControlObjectClient_getLastError
    func.restype = c_int
    func.argtypes = [ControlObjectClient]
    return func(client)

def ControlObjectClient_select(client):
    """
    Perform Select operation (SBO normal).
    
    Args:
        client: ControlObjectClient handle
        
    Returns:
        bool: True if successful
    """
    _check_lib()
    func = _lib.ControlObjectClient_select
    func.restype = c_bool
    func.argtypes = [ControlObjectClient]
    return bool(func(client))

def ControlObjectClient_selectWithValue(client, value):
    """
    Perform Select with value operation (SBO enhanced).
    
    Args:
        client: ControlObjectClient handle
        value: MmsValue to select with
        
    Returns:
        bool: True if successful
    """
    _check_lib()
    func = _lib.ControlObjectClient_selectWithValue
    func.restype = c_bool
    func.argtypes = [ControlObjectClient, MmsValue]
    return bool(func(client, value))

def ControlObjectClient_operate(client, value, oper_time=0):
    """
    Perform Operate operation.
    
    Args:
        client: ControlObjectClient handle
        value: MmsValue to operate with (must match type)
        oper_time: Optional uint64 timestamp (ms)
    
    Returns:
        bool: True if successful
    """
    _check_lib()
    func = _lib.ControlObjectClient_operate
    func.restype = c_bool
    func.argtypes = [ControlObjectClient, MmsValue, c_uint64] 
    return bool(func(client, value, int(oper_time)))

def ControlObjectClient_cancel(client):
    """
    Cancel selection.
    
    Args:
        client: ControlObjectClient handle
    
    Returns:
        bool: True if successful
    """
    try:
        _check_lib()
        func = _lib.ControlObjectClient_cancel
        func.restype = c_bool
        func.argtypes = [ControlObjectClient]
        return bool(func(client))
    except AttributeError:
        # Some older versions might not have cancel
        return False

def ControlObjectClient_setOriginator(client, identity, category):
    """
    Set the originator information.
    
    Args:
        client: ControlObjectClient handle
        identity: String identity (e.g. "HMI")
        category: Integer category (e.g. 1=StationControl)
    """
    try:
        _check_lib()
        func = _lib.ControlObjectClient_setOrigin # native name is usually setOrigin
        func.restype = None
        func.argtypes = [ControlObjectClient, c_char_p, c_int]
        func(client, _encode_str(identity), int(category))
    except AttributeError:
        # Try alternate name if setOrigin not found
        try:
            func = _lib.ControlObjectClient_setOriginator
            func.restype = None
            func.argtypes = [ControlObjectClient, c_int, c_char_p]
            func(client, int(category), _encode_str(identity))
        except AttributeError:
            logger.error("ControlObjectClient_setOriginator/setOrigin not found in library.")

def ControlObjectClient_setInterlockCheck(client, value):
    """Set Interlock Check flag."""
    try:
        _check_lib()
        func = _lib.ControlObjectClient_setInterlockCheck
        func.restype = None
        func.argtypes = [ControlObjectClient, c_bool]
        func(client, value)
        return True
    except AttributeError:
        return False

def ControlObjectClient_setSynchroCheck(client, value):
    """Set Synchro Check flag."""
    try:
        _check_lib()
        func = _lib.ControlObjectClient_setSynchroCheck
        func.restype = None
        func.argtypes = [ControlObjectClient, c_bool]
        func(client, value)
        return True
    except AttributeError:
        return False

def ControlObjectClient_setTestMode(client, value):
    """Set Test Mode (simulates test flag without using the Operate arg)."""
    try:
        _check_lib()
        func = _lib.ControlObjectClient_setTestMode
        func.restype = None
        func.argtypes = [ControlObjectClient, c_bool]
        func(client, value)
        return True
    except AttributeError:
        # Fallback is to use the operate argument
        return False

# ============================================================================
# MMS Value Functions
# ============================================================================

def MmsValue_getType(value):
    """
    Get the type of an MmsValue.
    
    Args:
        value: MmsValue handle
    
    Returns:
        int: MMS type constant (MMS_BOOLEAN, MMS_FLOAT, etc.)
    """
    _check_lib()
    func = _lib.MmsValue_getType
    func.restype = c_int
    func.argtypes = [MmsValue]
    return func(value)

def MmsValue_delete(value):
    """
    Delete an MmsValue and free memory.
    
    Args:
        value: MmsValue handle
    """
    if not value:
        return
    _check_lib()
    func = _lib.MmsValue_delete
    func.restype = None
    func.argtypes = [MmsValue]
    func(value)

def MmsValue_getBoolean(value):
    """Get boolean value from MmsValue."""
    _check_lib()
    func = _lib.MmsValue_getBoolean
    func.restype = c_bool
    func.argtypes = [MmsValue]
    return bool(func(value))

def MmsValue_toFloat(value):
    """Convert MmsValue to float."""
    _check_lib()
    func = _lib.MmsValue_toFloat
    func.restype = c_float
    func.argtypes = [MmsValue]
    return float(func(value))

def MmsValue_toInt32(value):
    """Convert MmsValue to int32."""
    _check_lib()
    func = _lib.MmsValue_toInt32
    func.restype = c_int32
    func.argtypes = [MmsValue]
    return int(func(value))

def MmsValue_toInt64(value):
    """Convert MmsValue to int64."""
    _check_lib()
    func = _lib.MmsValue_toInt64
    func.restype = c_int64
    func.argtypes = [MmsValue]
    return int(func(value))

def MmsValue_toUint32(value):
    """Convert MmsValue to uint32."""
    _check_lib()
    func = _lib.MmsValue_toUint32
    func.restype = c_uint32
    func.argtypes = [MmsValue]
    return int(func(value))

def MmsValue_toString(value):
    """Convert MmsValue to string."""
    _check_lib()
    func = _lib.MmsValue_toString
    func.restype = c_char_p
    func.argtypes = [MmsValue]
    result = func(value)
    return _decode_str(result)

def MmsValue_toUnixTimestamp(value):
    """Convert MmsValue UTC time to Unix timestamp."""
    _check_lib()
    func = _lib.MmsValue_toUnixTimestamp
    func.restype = c_uint64
    func.argtypes = [MmsValue]
    return int(func(value)) / 1000.0  # Convert milliseconds to seconds

def MmsValue_getBitStringSize(value):
    """Get size of bit string in bits."""
    _check_lib()
    func = _lib.MmsValue_getBitStringSize
    func.restype = c_int
    func.argtypes = [MmsValue]
    return func(value)

def MmsValue_getBitStringBit(value, bit_pos):
    """Get specific bit from bit string."""
    _check_lib()
    func = _lib.MmsValue_getBitStringBit
    func.restype = c_bool
    func.argtypes = [MmsValue, c_int]
    return bool(func(value, bit_pos))

def MmsValue_getArraySize(value):
    """Get size of array."""
    _check_lib()
    func = _lib.MmsValue_getArraySize
    func.restype = c_int
    func.argtypes = [MmsValue]
    return func(value)

def MmsValue_newBoolean(value):
    """Create new boolean MmsValue."""
    _check_lib()
    func = _lib.MmsValue_newBoolean
    func.restype = MmsValue
    func.argtypes = [c_bool]
    return func(bool(value)) # Force boolean

def MmsValue_newBitString(size):
    """Create new bit string MmsValue."""
    _check_lib()
    func = _lib.MmsValue_newBitString
    func.restype = MmsValue
    func.argtypes = [c_int]
    return func(size)

def MmsValue_setBitStringBit(value, bit_pos, bit_value):
    """Set bit in bit string."""
    if not value: return
    _check_lib()
    func = _lib.MmsValue_setBitStringBit
    func.restype = None
    func.argtypes = [MmsValue, c_int, c_bool]
    func(value, bit_pos, bool(bit_value))

def MmsValue_newFloat(value):
    """Create new float MmsValue."""
    _check_lib()
    func = _lib.MmsValue_newFloat
    func.restype = MmsValue
    func.argtypes = [c_float]
    return func(value)

def MmsValue_newInt32(value):
    """Create new int32 MmsValue."""
    _check_lib()
    func = _lib.MmsValue_newIntegerFromInt32
    func.restype = MmsValue
    func.argtypes = [c_int32]
    return func(value)

def MmsValue_newVisibleString(value):
    """Create new visible string MmsValue."""
    _check_lib()
    func = _lib.MmsValue_newVisibleString
    func.restype = MmsValue
    func.argtypes = [c_char_p]
    return func(_encode_str(value))

def MmsValue_newOctetString(size, max_size=None):
    """Create new empty octet string MmsValue."""
    _check_lib()
    if max_size is None:
        max_size = size
    func = _lib.MmsValue_newOctetString
    func.restype = MmsValue
    func.argtypes = [c_int, c_int]
    return func(size, max_size)

def MmsValue_setOctetString(value, buf, length=None):
    """Set content of OctetString."""
    _check_lib()
    func = _lib.MmsValue_setOctetString
    func.restype = None
    func.argtypes = [MmsValue, c_void_p, c_int]
    if length is None:
        length = len(buf)
    
    # Ensure bytes
    if isinstance(buf, str):
        buf = buf.encode('utf-8')
    
    func(value, buf, length)

def MmsValue_newStructure(size):
    """Create new empty Structure MmsValue."""
    _check_lib()
    # MmsValue_createEmptyStructure is safer than MmsValue_newStructure (which requires type spec)
    try:
        func = _lib.MmsValue_createEmptyStructure
        func.restype = MmsValue
        func.argtypes = [c_int]
        return func(size)
    except AttributeError:
        # If this doesn't exist, we cannot safely create an empty structure by size alone
        logger.error("MmsValue_createEmptyStructure not found in library.")
        return None

def MmsValue_setElement(complex_value, index, element_value):
    """Set element in a structure/array."""
    if not complex_value:
        return
    _check_lib()
    func = _lib.MmsValue_setElement
    func.restype = None
    func.argtypes = [MmsValue, c_int, MmsValue]
    func(complex_value, index, element_value)

def MmsValue_newUtcTime(timestamp_s):
    """Create new UTC Time MmsValue from unix timestamp (seconds)."""
    try:
        _check_lib()
        func = _lib.MmsValue_newUtcTime
        func.restype = MmsValue
        func.argtypes = [c_uint32]
        return func(int(timestamp_s))
    except AttributeError:
        logger.error("MmsValue_newUtcTime not found in library.")
        return None

def MmsValue_newUtcTimeMs(timestamp_ms):
    """Create new UTC Time MmsValue from unix timestamp (milliseconds)."""
    try:
        _check_lib()
        func = _lib.MmsValue_newUtcTimeMs
        func.restype = MmsValue
        func.argtypes = [c_uint64]
        mms_val = func(int(timestamp_ms))
        if mms_val:
            return mms_val
    except AttributeError:
        pass # Expected fallback
    
    # Fallback to second-resolution if Ms version not available or failed
    return MmsValue_newUtcTime(int(timestamp_ms / 1000))

def MmsValue_setUtcTime(mms_val, timestamp_s):
    """Set UTC time (seconds) in existing MmsValue."""
    if not mms_val: return
    try:
        _check_lib()
        func = _lib.MmsValue_setUtcTime
        func.restype = None
        func.argtypes = [MmsValue, c_uint32]
        func(mms_val, int(timestamp_s))
    except AttributeError:
        logger.error("MmsValue_setUtcTime not found in library.")

def MmsValue_setUtcTimeMs(mms_val, timestamp_ms):
    """Set high precision time in existing UtcTime value."""
    if not mms_val: return
    try:
        _check_lib()
        func = _lib.MmsValue_setUtcTimeMs
        func.restype = None
        func.argtypes = [MmsValue, c_uint64]
        func(mms_val, int(timestamp_ms))
    except AttributeError:
        # Fallback to second-resolution
        MmsValue_setUtcTime(mms_val, int(timestamp_ms / 1000))

def MmsValue_newInteger(value):
    """Create new Integer (auto-sized)."""
    _check_lib()
    func = _lib.MmsValue_newInteger
    func.restype = MmsValue
    func.argtypes = [c_int] # width in bits? Or value?
    # libiec61850 C API: MmsValue* MmsValue_newInteger(int size); -> Creates empty integer of size.
    # MmsValue* MmsValue_newIntegerFromInt32(int32_t value);
    # User assumes helper.
    # safe implementation:
    return MmsValue_newInt32(value)

# ============================================================================
# LinkedList Functions
# ============================================================================

def LinkedList_getData(list_element):
    """
    Get data from a linked list element.
    
    Args:
        list_element: LinkedList element
    
    Returns:
        c_void_p: Pointer to data (usually a string pointer)
    """
    _check_lib()
    func = _lib.LinkedList_getData
    func.restype = c_void_p
    func.argtypes = [LinkedList]
    return func(list_element)

def LinkedList_getNext(list_element):
    """
    Get next element in linked list.
    
    Args:
        list_element: LinkedList element
    
    Returns:
        LinkedList: Next element or None
    """
    _check_lib()
    func = _lib.LinkedList_getNext
    func.restype = LinkedList
    func.argtypes = [LinkedList]
    return func(list_element)

def LinkedList_destroy(list_head):
    """
    Destroy a linked list and free memory.
    
    Args:
        list_head: Head of LinkedList
    """
    _check_lib()
    func = _lib.LinkedList_destroy
    func.restype = None
    func.argtypes = [LinkedList]
    func(list_head)

def LinkedList_toStringList(linked_list):
    """
    Convert a LinkedList to a Python list of strings.
    
    This is a helper function that iterates through the linked list
    and extracts string values.
    
    Args:
        linked_list: LinkedList handle
    
    Returns:
        list: Python list of strings
    """
    result = []
    current = linked_list
    
    while current:
        data = LinkedList_getData(current)
        if data:
            # Cast void pointer to char pointer
            str_ptr = ctypes.cast(data, c_char_p)
            if str_ptr.value:
                result.append(_decode_str(str_ptr.value))
        current = LinkedList_getNext(current)
    
    return result

# ============================================================================
# Module Initialization Check
# ============================================================================

def is_library_loaded():
    """Check if the libiec61850 library was successfully loaded."""
    return HAS_LIBIEC61850

def get_load_error():
    """Get the error message if library failed to load."""
    if HAS_LIBIEC61850:
        return None
    return _LOAD_ERROR

def ControlObjectClient_setCommand(self, value):
    """
    Set the command value for the control object client.
    
    Args:
        self: ControlObjectClient handle
        value: MmsValue handle (ctlVal)
    """
    _check_lib()
    func = _lib.ControlObjectClient_setCommand
    func.restype = None
    func.argtypes = [c_void_p, MmsValue]
    func(self, value)
