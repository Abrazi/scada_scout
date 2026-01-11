
from pyiec61850 import iec61850
import inspect

print("Checking IedConnection methods:")
functions = [x for x in dir(iec61850) if x.startswith("IedConnection_")]
for f in functions:
    if "get" in f or "Get" in f:
        print(f)

print("\nChecking IedConnection_getLogicalDeviceList signature:")
try:
    print(inspect.signature(iec61850.IedConnection_getLogicalDeviceList))
except:
    print("Cannot get signature (C-extension)")
