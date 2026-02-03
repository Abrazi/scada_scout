import ctypes
import os

dll_path = r'c:\Users\majid\Documents\augment code\scada_scout\lib\iec61850.dll'
if not os.path.exists(dll_path):
    print(f"File not found: {dll_path}")
else:
    try:
        lib = ctypes.CDLL(dll_path)
        print(f"Successfully loaded: {lib}")
    except Exception as e:
        print(f"Error loading DLL: {e}")
