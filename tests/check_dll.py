import os
import platform
import ctypes

print("=== Checking libiec61850 DLL Status ===\n")

# Show search paths
print("1. System platform:", platform.system())
print("2. Python architecture:", platform.architecture())

# Check current directory
cwd = os.getcwd()
print(f"3. Current directory: {cwd}")

# Check lib folder
lib_folder = os.path.join(cwd, "lib")
print(f"4. Lib folder: {lib_folder}")
print(f"   Exists: {os.path.exists(lib_folder)}")

if os.path.exists(lib_folder):
    print("\n   Files in lib folder:")
    for f in os.listdir(lib_folder):
        if 'dll' in f.lower() or '61850' in f:
            full_path = os.path.join(lib_folder, f)
            size = os.path.getsize(full_path)
            print(f"     - {f} ({size:,} bytes)")

# Check where wrapper looks for DLL
wrapper_path = os.path.join(cwd, "src", "protocols", "iec61850", "iec61850_wrapper.py")
print(f"\n5. Wrapper file: {wrapper_path}")

# Try loading directly
print("\n6. Attempting direct DLL load:")
dll_names = ["iec61850.dll", "libiec61850.dll"]
search_paths = [
    lib_folder,
    cwd,
    os.path.join(cwd, "src", "protocols", "iec61850"),
]

for path in search_paths:
    for name in dll_names:
        dll_path = os.path.join(path, name)
        if os.path.exists(dll_path):
            print(f"\n   Found: {dll_path}")
            print(f"   Size: {os.path.getsize(dll_path):,} bytes")
            try:
                lib = ctypes.CDLL(dll_path)
                print(f"   ✅ Loaded successfully!")
                
                # Check if ConfigFileParser exists
                if hasattr(lib, 'ConfigFileParser_createModelFromConfigFileEx'):
                    print(f"   ✅ Has ConfigFileParser_createModelFromConfigFileEx")
                else:
                    print(f"   ⚠️ Missing ConfigFileParser_createModelFromConfigFileEx")
                    
            except Exception as e:
                print(f"   ❌ Failed to load: {e}")
