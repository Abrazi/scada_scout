import time

import pytest

# Skip unless both PySide6 and opcua are available in the test environment
pytest.importorskip("PySide6")
pytest.importorskip("opcua")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from src.ui.main_window import MainWindow
from src.core.device_manager import DeviceManager


def test_settings_toggle_starts_opc_mirror(qtbot):
    app = QApplication.instance() or QApplication([])
    # set opt-in QSettings
    settings = QSettings("ScadaScout", "UI")
    settings.setValue("opc_mirror_enabled", True)
    settings.setValue("opc_mirror_endpoint", "opc.tcp://127.0.0.1:4846")

    dm = DeviceManager()
    # create MainWindow and apply settings
    win = MainWindow(dm)
    qtbot.addWidget(win)

    # Apply settings and assert mirror started (or at least no exception)
    win._apply_settings()
    mirror = getattr(win, '_opc_mirror', None)
    assert mirror is not None

    # Basic smoke: mirror should be running and respond to stop
    try:
        assert hasattr(mirror, 'stop')
    finally:
        try:
            mirror.stop()
        except Exception:
            pass
        settings.setValue("opc_mirror_enabled", False)
