
from pyiec61850 import iec61850

try:
    print(f"ACSI_CLASS_DATA_OBJECT: {iec61850.ACSI_CLASS_DATA_OBJECT}")
except AttributeError:
    print("ACSI_CLASS_DATA_OBJECT not found")
