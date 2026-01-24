import sys
import os
from ctypes import byref, c_int

# Ensure src is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.protocols.iec61850 import iec61850_wrapper as iec61850

def check_pos_type():
    con = iec61850.IedConnection_create()
    error = iec61850.IedConnection_connect(con, "172.16.11.18", 102)
    
    if error != iec61850.IED_ERROR_OK:
        print(f"Failed to connect: {error}")
        return

    path = "GPS01ECB01CB1/CSWI1.Pos.stVal" # Read status value
    mms, err = iec61850.IedConnection_readObject(con, path, iec61850.IEC61850_FC_ST)
    if err == 0 and mms:
        mms_type = iec61850.MmsValue_getType(mms)
        print(f"Type of {path}: {mms_type} (3=BIT_STRING, 2=BOOLEAN, 4=INTEGER)")
        if mms_type == 3:
            size = iec61850.MmsValue_getBitStringSize(mms)
            print(f"BitString size: {size}")
        iec61850.MmsValue_delete(mms)
    else:
        print(f"Failed to read {path}: {err}")

    iec61850.IedConnection_close(con)
    iec61850.IedConnection_destroy(con)

if __name__ == "__main__":
    check_pos_type()
