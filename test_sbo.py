import time
import iec61850

ied_ip = "127.0.0.1"
tcp_port = 10002

con = iec61850.IedConnection_create()
error = iec61850.IedConnection_connect(con, ied_ip, tcp_port)

if error == iec61850.IED_ERROR_OK:
    print("Connected to IED successfully")

    # Select
    print("Sending Select...")
    err_select = iec61850.IedConnection_select(con, "ABBK3A03A1CTRL/CBCSWI1.Pos")
    print(f"Select result: {err_select}")

    # Operate
    print("Sending Operate (Close) with InterlockCheck=True...")
    ctl_val = iec61850.MmsValue_newBitString(2) # 10 = close
    iec61850.MmsValue_setBitStringBit(ctl_val, 0, 1) # bit 0 = 0? Wait, 2 is bit 1=1, bit 0=0 in normal? 
    # MmsValue_newBitString takes bit size. Let's use boolean if DPC operates often don't take bitstring in simple bindings
    # Actually wait. IEC61850 DPC operate usually takes boolean?
    pass
else:
    print("Failed to connect")

iec61850.IedConnection_destroy(con)
