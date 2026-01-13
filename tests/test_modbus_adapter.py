import pytest
from src.protocols.modbus.server_adapter import ModbusServerAdapter
from src.models.device_models import DeviceConfig, DeviceType


def test_modbus_adapter_connect_disconnect():
    config = DeviceConfig(
        name="TEST_MODBUS",
        device_type=DeviceType.MODBUS_SERVER,
        ip_address="127.0.0.1",
        port=5021,
        modbus_unit_id=1
    )

    adapter = ModbusServerAdapter(config)

    # Try connect; if pymodbus server not available, connect() should return False
    connected = adapter.connect()
    # connected can be True or False depending on environment; ensure disconnect does not raise
    try:
        adapter.disconnect()
    except Exception as e:
        pytest.fail(f"Disconnect raised exception: {e}")

    # If connected was True, ensure server is not running after disconnect
    if connected:
        assert not getattr(adapter.server, 'running', False)
