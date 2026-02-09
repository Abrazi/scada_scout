from typing import Optional

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from src.models.device_models import DeviceType
from src.ui.widgets.connection_dialog import ConnectionDialog
from src.ui.widgets.connection_progress_dialog import ConnectionProgressDialog


def add_device_via_dialog(
    parent,
    device_manager,
    connect_immediately_default: Optional[bool] = None,
    preset_device_type: Optional[DeviceType] = None,
    folder: str = "",
) -> Optional[str]:
    """Open the unified Add Device dialog and run the shared add/connect flow.

    Architectural: centralizes device creation so menu, toolbar, and context menu
    share the same UI and backend behavior.
    """
    dialog = ConnectionDialog(
        parent,
        connect_immediately_default=connect_immediately_default,
        preset_device_type=preset_device_type,
    )
    if folder:
        dialog.folder_input.setText(folder)

    if not dialog.exec():
        return None

    config = dialog.get_config()
    try:
        device_manager.add_device(config)
    except Exception as e:
        QMessageBox.critical(parent, "Error", f"Could not add device: {e}")
        return None

    if dialog.get_connect_immediately():
        _connect_with_progress(device_manager, config.name, parent)

    return config.name


def _connect_with_progress(device_manager, device_name: str, parent) -> None:
    """Connect to a device using the shared progress dialog."""
    progress_dialog = ConnectionProgressDialog(device_name, parent)
    device_manager.connection_progress.connect(
        lambda name, msg, pct: progress_dialog.update_progress(msg, pct) if name == device_name else None
    )
    progress_dialog.retry_requested.connect(
        lambda: device_manager.connect_device(device_name)
    )
    QTimer.singleShot(100, lambda: device_manager.connect_device(device_name))
    progress_dialog.exec()
