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

    print("Connected. Discovering Logical Devices...")
    ld_list, err = iec61850.IedConnection_getLogicalDeviceList(con)
    if err == 0:
        lds = iec61850.LinkedList_toStringList(ld_list)
        print(f"Logical Devices: {lds}")
        
        for ld in lds:
            print(f"\nLD: {ld}")
            ln_list, err = iec61850.IedConnection_getLogicalDeviceDirectory(con, ld)
            if err == 0:
                lns = iec61850.LinkedList_toStringList(ln_list)
                print(f"  LNs: {lns}")
                for ln in lns:
                    if "CSWI" in ln:
                        print(f"    Checking {ld}/{ln}...")
                        do_list, err = iec61850.IedConnection_getLogicalNodeDirectory(con, f"{ld}/{ln}", iec61850.ACSI_CLASS_DATA_OBJECT)
                        if err == 0:
                            dos = iec61850.LinkedList_toStringList(do_list)
                            print(f"      DOs: {dos}")
                            if "Pos" in dos:
                                print(f"      [FOUND Pos in {ld}/{ln}]")
                                # Read ctlModel
                                res = iec61850.IedConnection_readInt32Value(con, f"{ld}/{ln}.Pos.ctlModel", iec61850.IEC61850_FC_CF)
                                print(f"      Pos.ctlModel (CF): {res}")
                                res = iec61850.IedConnection_readInt32Value(con, f"{ld}/{ln}.Pos.ctlModel", iec61850.IEC61850_FC_ST)
                                print(f"      Pos.ctlModel (ST): {res}")
                        else:
                            print(f"      Failed to get DOs: {err}")
            else:
                print(f"  Failed to get LNs: {err}")
    else:
        print(f"Failed to get LD list: {err}")

    iec61850.IedConnection_close(con)
    iec61850.IedConnection_destroy(con)

if __name__ == "__main__":
    discover()
