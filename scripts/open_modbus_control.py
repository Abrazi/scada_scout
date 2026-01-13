import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.device_manager import DeviceManager
from src.ui.dialogs.modbus_control_dialog import ModbusControlDialog
import logging

logging.basicConfig(level=logging.INFO)

app = QApplication(sys.argv)

dm = DeviceManager()
# Try to load existing configuration (devices.json)
dm.load_configuration()

# Prefer a Modbus device if present
devices = dm.get_all_devices()
modbus_name = None
for d in devices:
    if d.config.device_type.name.startswith('MODBUS'):
        modbus_name = d.config.name
        break

if not modbus_name:
    print('No Modbus device found in configuration.')
    sys.exit(1)

# Ensure protocol exists (will create adapter)
proto = dm.get_or_create_protocol(modbus_name)
if not proto:
    print('Protocol adapter could not be created for', modbus_name)
    sys.exit(1)

# If adapter supports starting a server, attempt to start and wait for it
try:
    if hasattr(proto, 'connect'):
        # Some adapters return bool; others may start in background. Call and wait briefly.
        ok = proto.connect()
        # If boolean False returned, report and continue
        if ok is False:
            print('Adapter.connect() returned False; server may not be running')

        # If this is a server adapter exposing `server.running`, wait a short time for startup
        import time
        for _ in range(10):
            srv = getattr(proto, 'server', None)
            if srv and getattr(srv, 'running', False):
                break
            time.sleep(0.1)
except Exception as e:
    print('Adapter connect failed:', e)

# Show dialog
dlg = ModbusControlDialog(modbus_name, dm)
dlg.exec()

sys.exit(0)
