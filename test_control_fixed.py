"""
IEC 61850 SBO Control - Integration Guide and Test Script

This script demonstrates how to use the fixed IEC61850ControlClient
and provides comprehensive testing for SBO control operations.

Usage:
    python test_control_fixed.py <ied_ip> <control_ref> <value>
    
Example:
    python test_control_fixed.py 192.168.1.100 LD0/CSWI1.Pos True
"""

import sys
import logging
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from protocols.iec61850 import iec61850_wrapper as iec61850
from protocols.iec61850.control_client_fixed import (
    IEC61850ControlClient, 
    ControlParameters, 
    ControlModel
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_control_discovery(connection, control_ref: str):
    """
    Test 1: Control Object Discovery
    
    Verifies that the control object exists and discovers its capabilities.
    """
    print("\n" + "="*70)
    print("TEST 1: Control Object Discovery")
    print("="*70)
    
    try:
        # Read control model
        ctlmodel_ref = f"{control_ref}.ctlModel"
        value, error = iec61850.IedConnection_readInt32Value(
            connection, ctlmodel_ref, iec61850.IEC61850_FC_CF
        )
        
        if error != iec61850.IED_ERROR_OK:
            print(f"✗ Failed to read ctlModel: error={error}")
            return False
        
        print(f"✓ Control object found: {control_ref}")
        print(f"  ctlModel: {value} ({ControlModel.to_string(value)})")
        print(f"  SBO required: {ControlModel.is_sbo(value)}")
        print(f"  Enhanced security: {ControlModel.is_enhanced(value)}")
        
        # Check for Oper structure
        oper_path = f"{control_ref}.Oper.ctlVal"
        _, error = iec61850.IedConnection_readBooleanValue(
            connection, oper_path, iec61850.IEC61850_FC_ST
        )
        
        if error == iec61850.IED_ERROR_OK:
            print(f"✓ Oper.ctlVal accessible")
        else:
            print(f"⚠ Oper.ctlVal not accessible (error={error})")
        
        # Check for SBOw structure (if SBO model)
        if ControlModel.is_sbo(value):
            sbow_path = f"{control_ref}.SBOw"
            ret = iec61850.IedConnection_getDataDirectory(connection, sbow_path)
            children = ret[0] if isinstance(ret, (list, tuple)) else ret
            if children:
                print(f"✓ SBOw structure found")
                try:
                    iec61850.LinkedList_destroy(children)
                except:
                    pass
            else:
                print(f"⚠ SBOw structure not found")
        
        return True
    except Exception as e:
        print(f"✗ Exception during discovery: {e}")
        return False


def test_read_current_value(connection, control_ref: str):
    """
    Test 2: Read Current Control Value
    
    Reads the current status of the control object.
    """
    print("\n" + "="*70)
    print("TEST 2: Read Current Control Value")
    print("="*70)
    
    try:
        # Try to read stVal (status value)
        stval_ref = f"{control_ref}.stVal"
        value, error = iec61850.IedConnection_readBooleanValue(
            connection, stval_ref, iec61850.IEC61850_FC_ST
        )
        
        if error == iec61850.IED_ERROR_OK:
            print(f"✓ Current stVal: {value}")
            return value
        else:
            # Try reading as integer (some controls use integers)
            value, error = iec61850.IedConnection_readInt32Value(
                connection, stval_ref, iec61850.IEC61850_FC_ST
            )
            if error == iec61850.IED_ERROR_OK:
                print(f"✓ Current stVal: {value}")
                return value
            else:
                print(f"⚠ Could not read stVal: error={error}")
                return None
    except Exception as e:
        print(f"✗ Exception reading stVal: {e}")
        return None


def test_fixed_control_client(connection, control_ref: str, value):
    """
    Test 3: Fixed Control Client (Automatic Mode)
    
    Uses the new IEC61850ControlClient with automatic SBO handling.
    """
    print("\n" + "="*70)
    print("TEST 3: Fixed Control Client (Automatic Mode)")
    print("="*70)
    
    try:
        # Create control client
        client = IEC61850ControlClient(connection)
        
        # Set custom originator
        client.set_originator("test_script", 3)
        
        print(f"Attempting to control {control_ref} to {value}")
        
        # Perform control (automatic SBO handling)
        success = client.control(control_ref, value)
        
        if success:
            print(f"✓ Control operation SUCCESSFUL")
            return True
        else:
            print(f"✗ Control operation FAILED")
            return False
    except Exception as e:
        print(f"✗ Exception during control: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_manual_sbo_sequence(connection, control_ref: str, value):
    """
    Test 4: Manual SBO Sequence
    
    Performs explicit Select → Operate sequence for detailed testing.
    """
    print("\n" + "="*70)
    print("TEST 4: Manual SBO Sequence")
    print("="*70)
    
    try:
        client = IEC61850ControlClient(connection)
        
        # Read control model
        ctl_model = client.read_ctl_model(control_ref)
        print(f"Control model: {ctl_model} ({ControlModel.to_string(ctl_model)})")
        
        if ctl_model == ControlModel.STATUS_ONLY:
            print("✗ Control not allowed (status-only)")
            return False
        
        # Check if SBO is required
        if ControlModel.is_sbo(ctl_model):
            print(f"\n→ Step 1: SELECT")
            
            # Perform select (enhanced uses selectWithValue)
            if ControlModel.is_enhanced(ctl_model):
                success = client.select_with_value(control_ref, value)
            else:
                success = client.select(control_ref)
            
            if not success:
                print("✗ SELECT FAILED")
                return False
            
            print("✓ SELECT SUCCESS")
        else:
            print("ℹ Direct control - no select required")
        
        # Perform operate
        print(f"\n→ Step 2: OPERATE")
        success = client.operate(control_ref, value)
        
        if success:
            print("✓ OPERATE SUCCESS")
            return True
        else:
            print("✗ OPERATE FAILED")
            return False
    except Exception as e:
        print(f"✗ Exception during manual SBO: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_wrong_paths_for_comparison(connection, control_ref: str, value):
    """
    Test 5: Wrong Paths (For Comparison)
    
    Demonstrates what happens when using incorrect paths (as documented in the fix).
    """
    print("\n" + "="*70)
    print("TEST 5: Wrong Paths (Should Fail - For Comparison)")
    print("="*70)
    
    print("This test demonstrates the WRONG approach that was causing failures:")
    
    try:
        # ❌ WRONG: Writing directly to .ctlVal without .Oper
        wrong_path = f"{control_ref}.ctlVal"
        print(f"\n❌ Attempting WRONG path: {wrong_path}")
        
        error = iec61850.IedConnection_writeBooleanValue(
            connection, wrong_path, iec61850.IEC61850_FC_CO, value
        )
        
        if error == iec61850.IED_ERROR_OK:
            print(f"  Unexpectedly succeeded (device may be lenient)")
        else:
            print(f"  ✓ Failed as expected: error={error}")
        
        # ✅ CORRECT: Writing to .Oper.ctlVal
        correct_path = f"{control_ref}.Oper.ctlVal"
        print(f"\n✅ Attempting CORRECT path: {correct_path}")
        
        error = iec61850.IedConnection_writeBooleanValue(
            connection, correct_path, iec61850.IEC61850_FC_CO, value
        )
        
        if error == iec61850.IED_ERROR_OK:
            print(f"  ✓ Succeeded (but may still need SELECT first for SBO)")
        else:
            print(f"  Failed: error={error} (may need SELECT first)")
        
    except Exception as e:
        print(f"Exception: {e}")


def verify_control_result(connection, control_ref: str, expected_value):
    """
    Verify the control operation result by reading back the status
    """
    print("\n" + "="*70)
    print("VERIFICATION: Read Back Status")
    print("="*70)
    
    import time
    time.sleep(0.5)  # Give IED time to process
    
    try:
        stval_ref = f"{control_ref}.stVal"
        value, error = iec61850.IedConnection_readBooleanValue(
            connection, stval_ref, iec61850.IEC61850_FC_ST
        )
        
        if error == iec61850.IED_ERROR_OK:
            if value == expected_value:
                print(f"✓ VERIFICATION SUCCESS: stVal = {value} (matches expected)")
                return True
            else:
                print(f"✗ VERIFICATION FAILED: stVal = {value} (expected {expected_value})")
                return False
        else:
            print(f"⚠ Could not read stVal for verification: error={error}")
            return None
    except Exception as e:
        print(f"✗ Exception during verification: {e}")
        return None


def main():
    """Main test execution"""
    if len(sys.argv) < 4:
        print("Usage: python test_control_fixed.py <ied_ip> <control_ref> <value>")
        print("")
        print("Example:")
        print("  python test_control_fixed.py 192.168.1.100 LD0/CSWI1.Pos True")
        print("")
        print("Arguments:")
        print("  ied_ip       : IP address of the IED")
        print("  control_ref  : Control object reference (e.g., LD0/CSWI1.Pos)")
        print("  value        : Control value (True/False for boolean, or integer)")
        return 1
    
    ied_ip = sys.argv[1]
    control_ref = sys.argv[2]
    value_str = sys.argv[3]
    
    # Parse value
    if value_str.lower() in ['true', '1', 'on', 'close']:
        value = True
    elif value_str.lower() in ['false', '0', 'off', 'open']:
        value = False
    else:
        try:
            value = int(value_str)
        except:
            print(f"Invalid value: {value_str}")
            return 1
    
    print("="*70)
    print("IEC 61850 SBO CONTROL TEST SUITE")
    print("="*70)
    print(f"IED IP:       {ied_ip}")
    print(f"Control Ref:  {control_ref}")
    print(f"Target Value: {value}")
    print("="*70)
    
    # Connect to IED
    print("\nConnecting to IED...")
    connection = iec61850.IedConnection_create()
    error = iec61850.IedConnection_connect(connection, ied_ip, 102)
    
    if error != iec61850.IED_ERROR_OK:
        print(f"✗ Connection failed: error={error}")
        iec61850.IedConnection_destroy(connection)
        return 1
    
    print(f"✓ Connected to {ied_ip}:102")
    
    try:
        # Run tests
        results = []
        
        # Test 1: Discovery
        results.append(("Discovery", test_control_discovery(connection, control_ref)))
        
        # Test 2: Read current value
        current_value = test_read_current_value(connection, control_ref)
        results.append(("Read Current Value", current_value is not None))
        
        # Test 3: Fixed control client (automatic)
        results.append(("Fixed Control Client", test_fixed_control_client(connection, control_ref, value)))
        
        # Verify result
        verification = verify_control_result(connection, control_ref, value)
        
        # Test 4: Manual SBO sequence (if first test failed, try this)
        if not results[-1][1]:
            print("\n⚠ Automatic control failed, trying manual sequence...")
            results.append(("Manual SBO Sequence", test_manual_sbo_sequence(connection, control_ref, value)))
            verification = verify_control_result(connection, control_ref, value)
        
        # Test 5: Wrong paths demonstration
        test_wrong_paths_for_comparison(connection, control_ref, value)
        
        # Print summary
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        
        for test_name, success in results:
            status = "✓ PASS" if success else "✗ FAIL"
            print(f"{status:8} - {test_name}")
        
        if verification is not None:
            status = "✓ PASS" if verification else "✗ FAIL"
            print(f"{status:8} - Verification")
        
        print("="*70)
        
        overall_success = all(r[1] for r in results) and verification
        if overall_success:
            print("\n✓✓✓ ALL TESTS PASSED ✓✓✓")
            return 0
        else:
            print("\n✗✗✗ SOME TESTS FAILED ✗✗✗")
            return 1
        
    finally:
        # Clean up
        print("\nClosing connection...")
        iec61850.IedConnection_close(connection)
        iec61850.IedConnection_destroy(connection)
        print("✓ Connection closed")


if __name__ == "__main__":
    sys.exit(main())
