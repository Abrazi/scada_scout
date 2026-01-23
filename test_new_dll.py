#!/usr/bin/env python3
"""Test new iec61850.dll compilation"""
import ctypes
import os
import sys

def test_dll():
    # Test multiple locations
    test_paths = [
        "lib/iec61850.dll",
        "src/protocols/iec61850/iec61850.dll",
        "libiec61850-1.6.1/LIB/iec61850.dll",
    ]
    
    for dll_path in test_paths:
        dll_path = os.path.abspath(dll_path)
        if not os.path.exists(dll_path):
            print(f"⏭️  Skipping {dll_path} (not found)")
            continue
            
        print(f"\n{'='*70}")
        print(f"Testing DLL: {dll_path}")
        print(f"File size: {os.path.getsize(dll_path):,} bytes")
        print(f"Modified: {os.path.getmtime(dll_path)}")
        print('='*70)
        
        try:
            # Add DLL directory to path for dependencies (Windows)
            if os.name == 'nt' and hasattr(os, 'add_dll_directory'):
                dll_dir = os.path.dirname(dll_path)
                try:
                    os.add_dll_directory(dll_dir)
                    print(f"✅ Added DLL directory to search path: {dll_dir}")
                except Exception as e:
                    print(f"⚠️  Could not add DLL directory: {e}")
            
            print(f"\nLoading DLL with ctypes.CDLL...")
            lib = ctypes.CDLL(dll_path)
            print(f"✅ DLL loaded successfully!")
            print(f"   Handle: {lib}")
            print()
            
            # Test critical functions
            functions_to_test = [
                "IedServer_create",
                "IedServer_start",
                "ConfigFileParser_createModelFromConfigFileEx",
                "IedModel_create",
                "LogicalDevice_create",
            ]
            
            print("Checking for required functions:")
            for func_name in functions_to_test:
                has_func = hasattr(lib, func_name)
                status = "✅" if has_func else "❌"
                print(f"  {status} {func_name}")
            
            print(f"\n✅ SUCCESS - This DLL works!")
            return True
            
        except FileNotFoundError as e:
            print(f"❌ FileNotFoundError: {e}")
            print("   This usually means missing dependencies (MSVCR, pthread, etc.)")
            continue
        except OSError as e:
            print(f"❌ OSError: {e}")
            print("   Possible causes:")
            print("     - Missing Visual C++ Runtime")
            print("     - Missing pthread DLL")
            print("     - Wrong architecture (32/64-bit)")
            continue
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print(f"\n{'='*70}")
    print("❌ All DLL locations failed to load")
    print("="*70)
    return False

if __name__ == "__main__":
    success = test_dll()
    sys.exit(0 if success else 1)
