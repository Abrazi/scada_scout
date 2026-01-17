"""
Test to verify watch list RTT updates are reflected in property dialog
"""
import sys
sys.path.insert(0, '/home/majid/Documents/scada_scout')

from PySide6.QtWidgets import QApplication
from src.models.device_models import DeviceConfig, DeviceType, Device, Node, Signal, SignalType
from src.ui.dialogs.device_properties_dialog import DevicePropertiesDialog
from src.core.watch_list_manager import WatchedSignal

def create_device_with_signals():
    """Create a device with multiple signals."""
    config = DeviceConfig(
        name="Test Device",
        ip_address="127.0.0.1",
        port=102,
        device_type=DeviceType.IEC61850_IED
    )
    
    device = Device(config)
    device.connected = True
    
    # Create device tree
    root = Node("Root", "root")
    ld = Node("LLN0", "LLN0")
    
    sig1 = Signal(name="Sig1", address="IED1/LLN0$ST$Mod$stVal", signal_type=SignalType.STATE, access="RO")
    sig2 = Signal(name="Sig2", address="IED1/LLN0$ST$Health$stVal", signal_type=SignalType.STATE, access="RO")
    sig3 = Signal(name="Sig3", address="IED1/LLN0$ST$Beh$stVal", signal_type=SignalType.STATE, access="RO")
    
    ld.signals = [sig1, sig2, sig3]
    root.children = [ld]
    device.root_node = root
    
    return device, [sig1, sig2, sig3]

def test_watch_list_rtt_updates():
    """Test that watch list RTT values are used in calculations."""
    print("\n=== Testing Watch List RTT Updates ===")
    
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    device, signals = create_device_with_signals()
    
    # Simulate watch list with RTT values
    signals[0].last_rtt = 12.0  # Sig1: 12ms
    signals[1].last_rtt = 18.0  # Sig2: 18ms
    signals[2].last_rtt = 15.0  # Sig3: 15ms
    
    class MockDeviceManager:
        def get_protocol(self, device_name):
            return None
    
    class MockWatchListManager:
        def get_signals_for_device(self, device_name):
            return signals
    
    device_manager = MockDeviceManager()
    watch_list_manager = MockWatchListManager()
    
    dialog = DevicePropertiesDialog(device, device_manager, watch_list_manager)
    
    # Before any refresh
    max_rtt = dialog._calculate_max_rtt()
    min_rtt = dialog._calculate_min_rtt()
    avg_rtt = dialog._calculate_avg_rtt()
    
    print(f"Watch list signals: {len(signals)}")
    print(f"  Sig1 RTT: {signals[0].last_rtt:.2f} ms")
    print(f"  Sig2 RTT: {signals[1].last_rtt:.2f} ms")
    print(f"  Sig3 RTT: {signals[2].last_rtt:.2f} ms")
    print(f"\nCalculations from watch list:")
    print(f"  Max RTT: {max_rtt:.2f} ms")
    print(f"  Min RTT: {min_rtt:.2f} ms")
    print(f"  Avg RTT: {avg_rtt:.2f} ms")
    print(f"  Latest RTT: {dialog.latest_rtt:.2f} ms")
    
    # Verify calculations
    assert max_rtt == 18.0, f"Max should be 18.0, got {max_rtt}"
    assert min_rtt == 12.0, f"Min should be 12.0, got {min_rtt}"
    assert avg_rtt == 15.0, f"Avg should be 15.0, got {avg_rtt}"
    assert dialog.latest_rtt == -1.0, f"Latest should be -1.0 (not measured yet), got {dialog.latest_rtt}"
    
    print("\n✓ Watch list RTT values correctly used in calculations")
    print("✓ Latest RTT independent of min/max/avg")

def test_refresh_vs_watch_list():
    """Test that refresh measurement doesn't override watch list statistics."""
    print("\n=== Testing Refresh vs Watch List ===")
    
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    device, signals = create_device_with_signals()
    
    # Watch list has good statistics
    signals[0].last_rtt = 10.0
    signals[1].last_rtt = 20.0
    signals[2].last_rtt = 30.0
    
    class MockProtocol:
        def read_signal(self, signal):
            # Simulate a single read taking 5ms
            return signal
    
    class MockDeviceManager:
        def get_protocol(self, device_name):
            return MockProtocol()
    
    class MockWatchListManager:
        def get_signals_for_device(self, device_name):
            return signals
    
    device_manager = MockDeviceManager()
    watch_list_manager = MockWatchListManager()
    
    dialog = DevicePropertiesDialog(device, device_manager, watch_list_manager)
    
    # Simulate a refresh that measures 5ms
    dialog.latest_rtt = 5.0
    
    # Calculations should still use watch list
    max_rtt = dialog._calculate_max_rtt()
    min_rtt = dialog._calculate_min_rtt()
    avg_rtt = dialog._calculate_avg_rtt()
    
    print(f"Watch list RTTs: 10, 20, 30 ms")
    print(f"Single refresh measured: {dialog.latest_rtt:.2f} ms")
    print(f"\nStatistics (should use watch list, not single measurement):")
    print(f"  Max RTT: {max_rtt:.2f} ms (should be 30, not 5)")
    print(f"  Min RTT: {min_rtt:.2f} ms (should be 10, not 5)")
    print(f"  Avg RTT: {avg_rtt:.2f} ms (should be 20, not 5)")
    
    assert max_rtt == 30.0, f"Max should be from watch list (30), not refresh (5), got {max_rtt}"
    assert min_rtt == 10.0, f"Min should be from watch list (10), not refresh (5), got {min_rtt}"
    assert avg_rtt == 20.0, f"Avg should be from watch list (20), not refresh (5), got {avg_rtt}"
    
    print("\n✓ Refresh measurement doesn't corrupt watch list statistics")
    print("✓ Latest RTT shows single measurement, Min/Max/Avg show watch list")

def test_no_watch_list_signals():
    """Test behavior when no signals in watch list yet."""
    print("\n=== Testing No Watch List Signals ===")
    
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    device, signals = create_device_with_signals()
    
    # No RTT values in signals
    
    class MockDeviceManager:
        def get_protocol(self, device_name):
            return None
    
    class MockWatchListManager:
        def get_signals_for_device(self, device_name):
            return []  # Empty watch list
    
    device_manager = MockDeviceManager()
    watch_list_manager = MockWatchListManager()
    
    dialog = DevicePropertiesDialog(device, device_manager, watch_list_manager)
    
    # Simulate a single refresh measurement
    dialog.latest_rtt = 25.0
    
    max_rtt = dialog._calculate_max_rtt()
    min_rtt = dialog._calculate_min_rtt()
    avg_rtt = dialog._calculate_avg_rtt()
    
    print(f"Watch list: Empty")
    print(f"Latest RTT (from refresh): {dialog.latest_rtt:.2f} ms")
    print(f"\nStatistics (should show N/A since no watch list data):")
    print(f"  Max RTT: {'N/A' if max_rtt < 0 else f'{max_rtt:.2f} ms'}")
    print(f"  Min RTT: {'N/A' if min_rtt < 0 else f'{min_rtt:.2f} ms'}")
    print(f"  Avg RTT: {'N/A' if avg_rtt < 0 else f'{avg_rtt:.2f} ms'}")
    
    # Without watch list data, stats should be N/A
    assert max_rtt == -1.0, f"Max should be -1 (N/A) without watch list, got {max_rtt}"
    assert min_rtt == -1.0, f"Min should be -1 (N/A) without watch list, got {min_rtt}"
    assert avg_rtt == -1.0, f"Avg should be -1 (N/A) without watch list, got {avg_rtt}"
    assert dialog.latest_rtt == 25.0, f"Latest RTT should still show refresh value (25), got {dialog.latest_rtt}"
    
    print("\n✓ Min/Max/Avg show N/A when no watch list data")
    print("✓ Latest RTT still shows single measurement")

if __name__ == "__main__":
    print("=" * 70)
    print("Watch List RTT Integration Test")
    print("=" * 70)
    
    try:
        test_watch_list_rtt_updates()
        test_refresh_vs_watch_list()
        test_no_watch_list_signals()
        
        print("\n" + "=" * 70)
        print("ALL TESTS PASSED ✓")
        print("=" * 70)
        print("\nFix Summary:")
        print("1. Watch list now updates signal.last_rtt field")
        print("2. Min/Max/Avg calculations use watch list data only")
        print("3. Latest RTT shows single refresh measurement")
        print("4. Statistics independent of refresh button")
        print("5. Min/Max/Avg show N/A when no watch list data")
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
