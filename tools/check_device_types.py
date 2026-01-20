from src.core.device_manager_core import DeviceManagerCore
from src.models.device_models import DeviceType

m = DeviceManagerCore('devices.json')
m.load_configuration()
for name, dev in m._devices.items():
    t = type(dev.config.device_type)
    val = getattr(dev.config.device_type, 'value', None)
    print(f"{name}: type={t.__name__}, value={val!r}, is_MODBUS_TCP={dev.config.device_type==DeviceType.MODBUS_TCP}, is_MODBUS_SERVER={dev.config.device_type==DeviceType.MODBUS_SERVER}")
