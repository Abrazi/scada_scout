"""
Test script for Modbus device properties dialog
Tests the enhanced Modbus tab with comprehensive information display
"""
import sys
import logging
from PySide6.QtWidgets import QApplication

# Set up path
sys.path.insert(0, '/home/majid/Documents/scada_scout')

from src.models.device_models import DeviceConfig, DeviceType, Device, ModbusRegisterMap, ModbusDataType, ModbusEndianness
from src.protocols.modbus.adapter import ModbusTCPAdapter
from src.ui.dialogs.device_properties_dialog import DevicePropertiesDialog

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_test_modbus_device():
    """Create a test Modbus TCP device with register maps."""
    config = DeviceConfig(
        name="Test Modbus Device",
        ip_address="127.0.0.1",
        port=502,
        device_type=DeviceType.MODBUS_TCP,
        modbus_unit_id=1,
        modbus_timeout=3.0,
        modbus_register_maps=[
            ModbusRegisterMap(
                name_prefix="Temperature",
                function_code=3,  # Read Holding Registers
                start_address=40001,
                count=10,
                data_type=ModbusDataType.FLOAT32,
                endianness=ModbusEndianness.BIG_ENDIAN,
                scale=0.1,
                offset=-50.0,
                description="Temperature Sensors"
            ),
            ModbusRegisterMap(
                name_prefix="Status",
                function_code=1,  # Read Coils
                start_address=0,
                count=16,
                data_type=ModbusDataType.BOOL,
                description="Status Flags"
            ),
            ModbusRegisterMap(
                name_prefix="Counter",
                function_code=4,  # Read Input Registers
                start_address=30001,
                count=5,
                data_type=ModbusDataType.UINT32,
                endianness=ModbusEndianness.LITTLE_ENDIAN,
                description="Counters"
            )
        ]
    )
    
    device = Device(config)
    protocol = ModbusTCPAdapter(config)
    
    return device, protocol

def test_get_device_info(protocol):
    """Test get_device_info method."""
    print("\n=== Testing get_device_info ===")
    info = protocol.get_device_info()
    
    print(f"Unit ID: {info['unit_id']}")
    print(f"Timeout: {info['timeout']}")
    print(f"Connected: {info['connected']}")
    print(f"Register Maps Count: {info['register_maps_count']}")
    print(f"Total Registers: {info['total_registers']}")
    print(f"Function Codes Used: {info['function_codes_used']}")
    
    assert info['unit_id'] == 1
    assert info['timeout'] == 3.0
    assert info['register_maps_count'] == 3
    assert info['total_registers'] == 31  # 10 + 16 + 5
    assert set(info['function_codes_used']) == {1, 3, 4}
    
    print("✓ get_device_info test passed")

def test_get_register_map_details(protocol):
    """Test get_register_map_details method."""
    print("\n=== Testing get_register_map_details ===")
    details = protocol.get_register_map_details()
    
    print(f"Found {len(details)} register maps")
    
    for detail in details:
        print(f"\nRegister Map: {detail['name']}")
        print(f"  Function Code: {detail['function_code']}")
        print(f"  Start Address: {detail['start_address']}")
        print(f"  Count: {detail['count']}")
        print(f"  Data Type: {detail['data_type']}")
        print(f"  Endianness: {detail['endianness']}")
        print(f"  Scale: {detail['scale']}")
        print(f"  Offset: {detail['offset']}")
    
    assert len(details) == 3
    assert details[0]['name'] == "Temperature"
    assert details[0]['scale'] == 0.1
    assert details[0]['offset'] == -50.0
    
    print("✓ get_register_map_details test passed")

def test_get_connection_stats(protocol):
    """Test get_connection_stats method."""
    print("\n=== Testing get_connection_stats ===")
    stats = protocol.get_connection_stats()
    
    print(f"Connected: {stats['connected']}")
    print(f"IP Address: {stats['ip_address']}")
    print(f"Port: {stats['port']}")
    print(f"Unit ID: {stats['unit_id']}")
    print(f"Timeout: {stats['timeout']}")
    print(f"pymodbus Available: {stats['pymodbus_available']}")
    
    assert stats['ip_address'] == "127.0.0.1"
    assert stats['port'] == 502
    
    print("✓ get_connection_stats test passed")

def test_properties_dialog(device, protocol):
    """Test the properties dialog with Modbus device."""
    print("\n=== Testing Properties Dialog ===")
    
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    # Mock device manager (minimal implementation)
    class MockDeviceManager:
        def get_protocol(self, device_name):
            return protocol
    
    device_manager = MockDeviceManager()
    
    # Create and show dialog
    dialog = DevicePropertiesDialog(device, device_manager)
    
    print(f"Dialog title: {dialog.windowTitle()}")
    print(f"Number of tabs: {dialog.tabs.count()}")
    
    # Check that Modbus tab exists
    modbus_tab_found = False
    for i in range(dialog.tabs.count()):
        tab_text = dialog.tabs.tabText(i)
        print(f"  Tab {i}: {tab_text}")
        if "Modbus" in tab_text:
            modbus_tab_found = True
    
    assert modbus_tab_found, "Modbus tab should be present"
    
    print("✓ Properties dialog test passed")
    
    # Show dialog for visual inspection (comment out for automated testing)
    # dialog.exec()

if __name__ == "__main__":
    print("=" * 60)
    print("Modbus Device Properties Test")
    print("=" * 60)
    
    device, protocol = create_test_modbus_device()
    
    try:
        test_get_device_info(protocol)
        test_get_register_map_details(protocol)
        test_get_connection_stats(protocol)
        test_properties_dialog(device, protocol)
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
