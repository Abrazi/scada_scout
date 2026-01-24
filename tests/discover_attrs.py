import sys
import os
import time
from ctypes import byref, c_int, cast, c_char_p

# Ensure src is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.protocols.iec61850 import iec61850_wrapper as iec61850

def discover():
    con = iec61850.IedConnection_create()
    error = iec61850.IedConnection_connect(con, "172.16.11.18", 102)
    
    if error != iec61850.IED_ERROR_OK:
        print(f"Failed to connect: {error}")
        return

    print("Connected.")
    ld = "GPS01ECB01CB1"
    ln = "CSWI1"
    do = "Pos"
    path = f"{ld}/{ln}.{do}"
    
    print(f"Checking data attributes for {path}...")
    # Try with FC=CO for control attributes
    dir_list, err = iec61850.IedConnection_getDataDirectoryByFC(con, path, iec61850.IEC61850_FC_CO)
    if err == 0:
        attrs = iec61850.LinkedList_toStringList(dir_list)
        print(f"Attributes (CO): {attrs}")
        iec61850.LinkedList_destroy(dir_list)
    else:
        print(f"Failed to get attributes (CO): {err}")

    # Try with FC=CF for config attributes
    dir_list, err = iec61850.IedConnection_getDataDirectoryByFC(con, path, iec61850.IEC61850_FC_CF)
    if err == 0:
        attrs = iec61850.LinkedList_toStringList(dir_list)
        print(f"Attributes (CF): {attrs}")
        iec61850.LinkedList_destroy(dir_list)
    else:
        print(f"Failed to get attributes (CF): {err}")

    # Try with FC=ST for status attributes
    dir_list, err = iec61850.IedConnection_getDataDirectoryByFC(con, path, iec61850.IEC61850_FC_ST)
    if err == 0:
        attrs = iec61850.LinkedList_toStringList(dir_list)
        print(f"Attributes (ST): {attrs}")
        iec61850.LinkedList_destroy(dir_list)
    else:
        print(f"Failed to get attributes (ST): {err}")

    iec61850.IedConnection_close(con)
    iec61850.IedConnection_destroy(con)

if __name__ == "__main__":
    discover()
