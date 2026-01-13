
try:
    from pyiec61850 import iec61850
    print("pyiec61850 found")
    print("Attributes in iec61850:")
    for attr in dir(iec61850):
        if "write" in attr.lower() or "control" in attr.lower() or "operate" in attr.lower():
            print(attr)
except ImportError:
    print("pyiec61850 not found")
