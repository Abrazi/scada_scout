import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication
from src.ui.widgets.connection_dialog import ConnectionDialog
from src.models.device_models import DeviceType


def test_connection_dialog_includes_opc_and_returns_endpoint(qtbot):
    app = QApplication.instance() or QApplication([])
    dlg = ConnectionDialog()
    qtbot.addWidget(dlg)

    # Ensure OPC entries present in protocol combo
    items = [dlg.type_input.itemData(i) for i in range(dlg.type_input.count())]
    assert DeviceType.OPC_UA_CLIENT in items or DeviceType.OPC_UA_SERVER in items

    # Select OPC UA Client and set endpoint
    idx = -1
    for i in range(dlg.type_input.count()):
        if dlg.type_input.itemData(i) == DeviceType.OPC_UA_CLIENT:
            idx = i
            break
    assert idx >= 0
    dlg.type_input.setCurrentIndex(idx)

    # Endpoint should be visible
    assert dlg.opc_endpoint_input.isVisible()
    dlg.opc_endpoint_input.setText("opc.tcp://127.0.0.1:4840")

    cfg = dlg.get_config()
    assert cfg.device_type == DeviceType.OPC_UA_CLIENT
    assert cfg.protocol_params.get('endpoint') == "opc.tcp://127.0.0.1:4840"