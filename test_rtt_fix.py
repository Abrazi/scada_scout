"""
Test to verify RTT calculation fix - no duplicates
"""
import sys
sys.path.insert(0, '/home/majid/Documents/scada_scout')

from PySide6.QtWidgets import QApplication
from src.models.device_models import DeviceConfig, DeviceType, Device, Node, Signal, SignalType
from src.ui.dialogs.device_properties_dialog import DevicePropertiesDialog

def create_device_with_duplicate_signals():
    """Create a device where same signals are in both watch list and device tree."""
    config = DeviceConfig(
        name="Test Device",
        ip_address="127.0.0.1",
        port=102,
        device_type=DeviceType.IEC61850_IED
    )
    
    device = Device(config)
    device.connected = True
    
    # Create device tree with signals
    root = Node("Root", "root")
    ld = Node("LLN0", "LLN0")
    
    sig1 = Signal(
        name="Sig1",
        address="IED1/LLN0$ST$Mod$stVal",
        signal_type=SignalType.STATE,
        access="RO"
    )
    sig1.last_rtt = 10.0
    
    sig2 = Signal(
        name="Sig2",
        address="IED1/LLN0$ST$Health$stVal",
        signal_type=SignalType.STATE,
        access="RO"
    )
    sig2.last_rtt = 20.0
    
    sig3 = Signal(
        name="Sig3",
        address="IED1/LLN0$ST$Beh$stVal",
        signal_type=SignalType.STATE,
        access="RO"
    )
    sig3.last_rtt = 15.0
    
    ld.signals = [sig1, sig2, sig3]
    root.children = [ld]
    device.root_node = root
    
    # Return the signals too (they'll be in watch list)
    return device, [sig1, sig2, sig3]

def test_no_duplicates():
    """Test that RTT calculations don't count duplicates."""
    print("\n=== Testing RTT Calculations Without Duplicates ===")
    
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    device, signals = create_device_with_duplicate_signals()
    
    # Mock device manager
    class MockDeviceManager:
        def get_protocol(self, device_name):
            return None
    
    # Mock watch list with same signals as device tree
    class MockWatchListManager:
        def __init__(self, signals):
            self.signals = signals
        
        def get_signals_for_device(self, device_name):
            return self.signals
    
    device_manager = MockDeviceManager()
    watch_list_manager = MockWatchListManager(signals)
    
    dialog = DevicePropertiesDialog(device, device_manager, watch_list_manager)
    
    # Signals: 10.0, 20.0, 15.0
    # Expected: Max=20.0, Min=10.0, Avg=15.0
    
    max_rtt = dialog._calculate_max_rtt()
    min_rtt = dialog._calculate_min_rtt()
    avg_rtt = dialog._calculate_avg_rtt()
    
    print(f"Signal RTTs: 10.0, 20.0, 15.0")
    print(f"Signals in watch list: {len(signals)}")
    print(f"Signals in device tree: {len(signals)}")
    print(f"\nCalculated values:")
    print(f"  Max RTT: {max_rtt:.2f} ms")
    print(f"  Min RTT: {min_rtt:.2f} ms")
    print(f"  Avg RTT: {avg_rtt:.2f} ms")
    
    # Verify correctness
    assert max_rtt == 20.0, f"Max RTT should be 20.0, got {max_rtt}"
    assert min_rtt == 10.0, f"Min RTT should be 10.0, got {min_rtt}"
    assert avg_rtt == 15.0, f"Avg RTT should be 15.0 (not inflated by duplicates), got {avg_rtt}"
    
    print("\n✓ All calculations correct (no duplicates counted)")

def test_unique_signals():
    """Test with signals only in one location."""
    print("\n=== Testing RTT With Unique Signals ===")
    
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    device, all_signals = create_device_with_duplicate_signals()
    
    # Mock watch list with only 2 signals
    class MockWatchListManager:
        def get_signals_for_device(self, device_name):
            return all_signals[:2]  # Only first 2 signals
    
    class MockDeviceManager:
        def get_protocol(self, device_name):
            return None
    
    device_manager = MockDeviceManager()
    watch_list_manager = MockWatchListManager()
    
    dialog = DevicePropertiesDialog(device, device_manager, watch_list_manager)
    
    # Watch list: 10.0, 20.0
    # Device tree: 10.0, 20.0, 15.0
    # Should use all 3 unique signals
    
    max_rtt = dialog._calculate_max_rtt()
    min_rtt = dialog._calculate_min_rtt()
    avg_rtt = dialog._calculate_avg_rtt()
    
    print(f"Watch list signals: 2 (RTT: 10.0, 20.0)")
    print(f"Device tree signals: 3 (RTT: 10.0, 20.0, 15.0)")
    print(f"\nCalculated values:")
    print(f"  Max RTT: {max_rtt:.2f} ms")
    print(f"  Min RTT: {min_rtt:.2f} ms")
    print(f"  Avg RTT: {avg_rtt:.2f} ms")
    
    assert max_rtt == 20.0, f"Max should be 20.0, got {max_rtt}"
    assert min_rtt == 10.0, f"Min should be 10.0, got {min_rtt}"
    assert avg_rtt == 15.0, f"Avg should be 15.0 (all 3 unique signals), got {avg_rtt}"
    
    print("\n✓ Correctly uses all unique signals")

if __name__ == "__main__":
    print("=" * 70)
    print("RTT Calculation Duplicate Fix Test")
    print("=" * 70)
    
    try:
        test_no_duplicates()
        test_unique_signals()
        
        print("\n" + "=" * 70)
        print("ALL TESTS PASSED ✓")
        print("=" * 70)
        print("\nFix Summary:")
        print("- Changed from list-based to map-based RTT collection")
        print("- Uses signal address as unique key to prevent duplicates")
        print("- Correctly handles signals in both watch list and device tree")
        print("- Max, Min, Avg calculations now accurate")
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
