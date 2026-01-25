import pytest

pytest.importorskip("PySide6")

from src.core.device_manager import DeviceManager
from src.ui.widgets.device_tree import DeviceTree
from src.models.device_models import DeviceConfig, DeviceType


class FakeDialog:
    def __init__(self, *a, **kw):
        self.folder_input = type('F', (), {'setText': lambda *a, **k: None})()
        self.opc_endpoint_input = type('F', (), {'setText': lambda *a, **k: None, 'setVisible': lambda *a, **k: None})()
        self.type_input = type('F', (), {'count': lambda *a: 0, 'setCurrentIndex': lambda *a: None})()
        self._cfg = DeviceConfig(
            name='OPCTest',
            ip_address='127.0.0.1',
            port=4840,
            device_type=DeviceType.OPC_UA_CLIENT,
            protocol_params={'endpoint': 'opc.tcp://127.0.0.1:4840'}
        )
    def exec(self):
        return True
    def get_config(self):
        return self._cfg


def test_quickadd_opc_client_invokes_add_device(monkeypatch, qtbot):
    dm = DeviceManager()
    tree = DeviceTree(dm)
    qtbot.addWidget(tree)

    # Replace ConnectionDialog in device_tree module with FakeDialog
    import src.ui.widgets.device_tree as dt_mod
    monkeypatch.setattr(dt_mod, 'ConnectionDialog', FakeDialog, raising=False)

    called = {}

    def fake_add_device(cfg):
        called['cfg'] = cfg
        return None

    dm.add_device = fake_add_device

    # Call helper
    tree._add_new_device_preselected('opc_client')

    assert 'cfg' in called
    assert isinstance(called['cfg'], DeviceConfig)
    assert called['cfg'].device_type == DeviceType.OPC_UA_CLIENT
    assert called['cfg'].protocol_params.get('endpoint') == 'opc.tcp://127.0.0.1:4840'