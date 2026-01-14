import ctypes
import os

def check_symbols():
    try:
        # Load the library (same logic as wrapper)
        lib_name = "libiec61850.so" # Adjust for Windows if needed
        import platform
        if platform.system() == "Windows":
            lib_name = "iec61850.dll"
            
        lib = ctypes.CDLL(lib_name)
        print(f"Library loaded: {lib}")
        
        symbols = [
            "ControlObjectClient_setOriginator",
            "ControlObjectClient_setInterlockCheck",
            "ControlObjectClient_setSynchroCheck",
            "ControlObjectClient_setTestMode",
            "ControlObjectClient_operate"
        ]
        
        for sym in symbols:
            try:
                func = getattr(lib, sym)
                print(f"✅ Found {sym}")
            except AttributeError:
                print(f"❌ Missing {sym}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_symbols()
