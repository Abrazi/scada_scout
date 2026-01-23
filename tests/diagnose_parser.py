import ctypes
from src.protocols.iec61850 import lib61850 as lib

# Test if ConfigFileParser function exists and works
print("Testing libiec61850 ConfigFileParser...")
print("=" * 60)

# 1. Check if function exists
if hasattr(lib, 'ConfigFileParser_createModelFromConfigFileEx'):
    print("✅ Function exists in library")
else:
    print("❌ Function NOT found in library!")
    exit(1)

# 2. Test with libiec61850's own example
test_file = r"c:\Users\majid\Documents\scadaScout\scada_scout\libiec61850\examples\server_example_basic_io\simpleIO_direct_control.icd"

print(f"\nTesting with libiec61850's own example:")
print(f"  {test_file}")

model = lib.ConfigFileParser_createModelFromConfigFileEx(test_file.encode('utf-8'))

if model:
    print("✅ SUCCESS - Parser works with libiec61850's own files")
    print("   Your DLL has working ConfigFileParser")
    lib.IedModel_destroy(model)
else:
    print("❌ CRITICAL: Parser FAILS even on libiec61850's own examples!")
    print("   Your libiec61850.dll is broken or incomplete")
    print("   Possible causes:")
    print("   - DLL compiled without file parsing support")
    print("   - Missing dependencies (libxml2, etc.)")
    print("   - Wrong DLL version")
    print("\n   SOLUTION: You need to recompile or get a proper libiec61850.dll")
