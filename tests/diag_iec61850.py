
import sys
import time
import logging

try:
    from pyiec61850 import iec61850
except ImportError:
    print("Error: pyiec61850 not found")
    sys.exit(1)

IP = "172.16.11.18"
PORT = 102

print(f"Connecting to {IP}:{PORT}...")
con = iec61850.IedConnection_create()
err = iec61850.IedConnection_connect(con, IP, PORT)

if err != iec61850.IED_ERROR_OK:
    print(f"Failed to connect: {err}")
    sys.exit(1)

print("Connected!")

print("-" * 20)
print("Calling IedConnection_getLogicalDeviceList...")
lds = iec61850.IedConnection_getLogicalDeviceList(con)
print(f"Result type: {type(lds)}")
print(f"Result repr: {repr(lds)}")

if lds:
    print(f"Is LinkedList? {'LinkedList' in str(type(lds))}")
    
    # Try iteration
    curr = lds
    count = 0
    while curr and count < 5:
        data = iec61850.LinkedList_getData(curr)
        print(f"Node {count}: data type={type(data)}, data repr={repr(data)}")
        
        # Try direct string conversion
        try:
             print(f"  str(data): {str(data)}")
        except:
             pass
             
        # Try ctypes if needed
        if data:
            import ctypes
            try:
                # Try getting address
                addr = 0
                if hasattr(data, "this"):
                     print(f"  Has .this: {data.this}")
                     addr = int(data.this)
                elif hasattr(data, "__int__"):
                     addr = int(data)
                
                if addr:
                    c_str = ctypes.cast(addr, ctypes.c_char_p)
                    print(f"  ctypes value: {c_str.value}")
            except Exception as e:
                print(f"  ctypes error: {e}")

        curr = iec61850.LinkedList_getNext(curr)
        count += 1
else:
    print("Result is None/Empty")

iec61850.IedConnection_close(con)
iec61850.IedConnection_destroy(con)
