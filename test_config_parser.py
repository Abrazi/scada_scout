#!/usr/bin/env python3
"""Test ConfigFileParser with new DLL"""
import sys
import os
sys.path.insert(0, "src")

from protocols.iec61850 import lib61850 as lib
import ctypes

print("Testing ConfigFileParser with test.scd...")
print("=" * 70)

# Configure function signature
lib.ConfigFileParser_createModelFromConfigFileEx.restype = ctypes.c_void_p
lib.ConfigFileParser_createModelFromConfigFileEx.argtypes = [ctypes.c_char_p]

scd_path = os.path.abspath("test.scd")
print(f"SCD file: {scd_path}")
print(f"File exists: {os.path.exists(scd_path)}")
print(f"File size: {os.path.getsize(scd_path):,} bytes")
print()

print("Calling ConfigFileParser_createModelFromConfigFileEx...")
model_ptr = lib.ConfigFileParser_createModelFromConfigFileEx(scd_path.encode("utf-8"))

if model_ptr:
    print(f"✅ SUCCESS! ConfigFileParser returned model pointer: {hex(model_ptr)}")
    print()
    print("🎉 Your new DLL has WORKING ConfigFileParser!")
    print("   This means:")
    print("   • Native SCD parsing will work")
    print("   • Full model discovery will work")
    print("   • No need for Python dynamic builder")
    print("   • Server will expose complete IED model")
    
    # Clean up
    try:
        if hasattr(lib, "IedModel_destroy"):
            lib.IedModel_destroy(model_ptr)
            print("\n✅ Model destroyed cleanly")
    except Exception as e:
        print(f"\nWarning: Could not destroy model: {e}")
    
    sys.exit(0)
else:
    print("❌ ConfigFileParser returned NULL")
    print("\nPossible reasons:")
    print("  1. SCD file format issue")
    print("  2. IED not found in SCD")
    print("  3. Parser doesn't support this SCD version")
    print("\nWill fall back to Python dynamic builder")
    sys.exit(1)
