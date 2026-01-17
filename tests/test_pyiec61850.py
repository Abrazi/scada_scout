
from pyiec61850 import iec61850

print(f"iec61850 module loaded: {iec61850}")
try:
    con = iec61850.IedConnection_create()
    print("IedConnection_create success")
    iec61850.IedConnection_destroy(con)
    print("IedConnection_destroy success")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
