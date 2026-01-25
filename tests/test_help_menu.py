import os

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl

from src.ui.main_window import MainWindow
from src.core.device_manager import DeviceManager


def test_open_help_file_uses_qdesktopservices(monkeypatch, qtbot):
    app = QApplication.instance() or QApplication([])
    dm = DeviceManager()
    win = MainWindow(dm)
    qtbot.addWidget(win)

    called = {}

    def fake_open(url: QUrl):
        called['url'] = url
        return True

    monkeypatch.setattr(QDesktopServices, 'openUrl', staticmethod(fake_open))

    win._open_help_file()

    assert 'url' in called, "QDesktopServices.openUrl was not called"
    path = called['url'].toLocalFile()
    assert os.path.basename(path).lower().startswith('readme'), f"expected README, got {path}"


def test_open_scripting_guide_uses_qdesktopservices(monkeypatch, qtbot):
    app = QApplication.instance() or QApplication([])
    dm = DeviceManager()
    win = MainWindow(dm)
    qtbot.addWidget(win)

    called = {}

    def fake_open(url: QUrl):
        called['url'] = url
        return True

    monkeypatch.setattr(QDesktopServices, 'openUrl', staticmethod(fake_open))

    win._open_scripting_guide()

    assert 'url' in called, "QDesktopServices.openUrl was not called"
    path = called['url'].toLocalFile()
    assert path.endswith(os.path.join('docs', 'script_user_guide.md')) or path.endswith('script_user_guide.md')
