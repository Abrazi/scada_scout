"""
Test script to verify IEC 61850 wrapper is correctly loaded.

This script tests:
1. Import of iec61850_wrapper module
2. Library loading status
3. Basic API availability
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_wrapper_import():
    """Test that iec61850_wrapper can be imported."""
    print("Test 1: Importing iec61850_wrapper...")
    try:
        from src.protocols.iec61850 import iec61850_wrapper
        print("✓ Module imported successfully")
        return True, iec61850_wrapper
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False, None

def test_library_loaded(wrapper):
    """Test if libiec61850 library is loaded."""
    print("\nTest 2: Checking library load status...")
    try:
        if wrapper.is_library_loaded():
            print("✓ libiec61850 library is loaded")
            return True
        else:
            print("✗ libiec61850 library is NOT loaded")
            print(f"  Error: {wrapper.get_load_error()}")
            return False
    except Exception as e:
        print(f"✗ Error checking library status: {e}")
        return False

def test_api_availability(wrapper):
    """Test that key API functions are available."""
    print("\nTest 3: Checking API availability...")
    
    required_functions = [
        'IedConnection_create',
        'IedConnection_destroy', 
        'IedConnection_connect',
        'IedConnection_close',
        'IedConnection_readFloatValue',
        'IedConnection_readBooleanValue',
        'IedConnection_getLogicalDeviceList',
        'MmsValue_delete',
        'LinkedList_toStringList',
    ]
    
    all_ok = True
    for func_name in required_functions:
        if hasattr(wrapper, func_name):
            print(f"  ✓ {func_name}")
        else:
            print(f"  ✗ {func_name} NOT FOUND")
            all_ok = False
    
    if all_ok:
        print("✓ All required API functions available")
    else:
        print("✗ Some API functions are missing")
    
    return all_ok

def test_error_constants(wrapper):
    """Test that error constants are defined."""
    print("\nTest 4: Checking error constants...")
    
    required_constants = [
        'IED_ERROR_OK',
        'IED_STATE_CONNECTED',
        'IEC61850_FC_ST',
        'IEC61850_FC_MX',
        'MMS_FLOAT',
        'MMS_BOOLEAN',
    ]
    
    all_ok = True
    for const_name in required_constants:
        if hasattr(wrapper, const_name):
            value = getattr(wrapper, const_name)
            print(f"  ✓ {const_name} = {value}")
        else:
            print(f"  ✗ {const_name} NOT FOUND")
            all_ok = False
    
    if all_ok:
        print("✓ All required constants available")
    else:
        print("✗ Some constants are missing")
    
    return all_ok

def test_adapter_import():
    """Test that adapter can import the new wrapper."""
    print("\nTest 5: Importing IEC61850Adapter...")
    try:
        from src.protocols.iec61850.adapter import IEC61850Adapter
        print("✓ Adapter imported successfully")
        return True
    except Exception as e:
        print(f"✗ Adapter import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("IEC 61850 Wrapper Verification Test")
    print("=" * 60)
    
    results = []
    
    # Test 1: Import
    success, wrapper = test_wrapper_import()
    results.append(("Import wrapper", success))
    
    if not success:
        print("\n✗ Cannot proceed - wrapper import failed")
        print_summary(results)
        return 1
    
    # Test 2: Library loading
    success = test_library_loaded(wrapper)
    results.append(("Library loaded", success))
    
    if not success:
        print("\n⚠ WARNING: Library not loaded")
        print("  This is expected if libiec61850 is not yet installed on your system.")
        print("  See IEC61850_SETUP.md for installation instructions.")
    
    # Test 3: API availability
    success = test_api_availability(wrapper)
    results.append(("API available", success))
    
    # Test 4: Constants
    success = test_error_constants(wrapper)
    results.append(("Constants defined", success))
    
    # Test 5: Adapter
    success = test_adapter_import()
    results.append(("Adapter import", success))
    
    # Summary
    print_summary(results)
    
    # Return status
    all_passed = all(result[1] for result in results)
    if all_passed:
        print("\n✓ ALL TESTS PASSED")
        return 0
    else:
        print("\n✗ SOME TESTS FAILED")
        return 1

def print_summary(results):
    """Print test summary."""
    print("\n" + "=" * 60)
    print("Test Summary:")
    print("=" * 60)
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name:.<50} {status}")
    print("=" * 60)

if __name__ == "__main__":
    sys.exit(main())
