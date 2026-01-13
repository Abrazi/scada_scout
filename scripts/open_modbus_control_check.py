import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
import logging

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.device_manager import DeviceManager
from src.ui.dialogs.modbus_control_dialog import ModbusControlDialog

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

proto = dm.get_or_create_protocol(modbus_name)
try:
    if hasattr(proto, 'connect') and not getattr(proto, 'connected', False):
        proto.connect()
except Exception as e:
    print('Adapter connect failed:', e)

print('Server running BEFORE dialog:', getattr(proto.server, 'running', False))

# Show dialog
dlg = ModbusControlDialog(modbus_name, dm)
# Use non-blocking show to allow programmatic close if needed
# But for now, exec() so user can manually close it
dlg.exec()

# After dialog closed, print server state
print('Server running AFTER dialog:', getattr(proto.server, 'running', False))

# Keep process alive briefly to observe background threads if any
import time
time.sleep(1)

sys.exit(0)
