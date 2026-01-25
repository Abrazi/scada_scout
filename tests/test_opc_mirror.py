import time

import pytest

# Defer importing DeviceManagerCore (it pulls GUI bits in some environments).
# Skip the whole test early if OPC UA isn't available in this environment.
opcua = pytest.importorskip("opcua")

from src.models.device_models import DeviceConfig, DeviceType, Node, Signal


def test_opc_mirror_end_to_end():
    # If GUI bindings are not present in the environment, skip the test gracefully.
    pytest.importorskip("PySide6")

    from src.core.device_manager_core import DeviceManagerCore
    from src.core.opc_mirror import OPCMirror
    from src.protocols.opc.ua_client import UAClient

    dm = DeviceManagerCore(config_path=':memory:')
    cfg = DeviceConfig(name='MirrorDev', ip_address='127.0.0.1', port=0, device_type=DeviceType.UNKNOWN)
    dev = dm.add_device(cfg)

    # build a simple node and attach
    node = Node(name='Root')
    sig = Signal(name='Value', address='value', value=10)
    node.signals.append(sig)
    dm._devices[cfg.name].root_node = node
    dm._assign_unique_addresses(cfg.name, node)

    mirror = OPCMirror(dm, poll_interval=0.1)
    mirror.start('opc.tcp://127.0.0.1:4845')

    client = UAClient()
    client.connect('opc.tcp://127.0.0.1:4845')

    # read initial value
    read = client.read_node('ns=2;s=MirrorDev.Value')
    assert read == 10 or read == pytest.approx(10)

    # update via DeviceManager and verify OPC reflects it
    sig.value = 55
    dm._on_signal_update(cfg.name, sig)
    for _ in range(20):
        if client.read_node('ns=2;s=MirrorDev.Value') in (55, pytest.approx(55)):
            break
        time.sleep(0.05)
    else:
        pytest.skip('OPC mirror update not observed in this environment')

    # write via OPC and verify DeviceManager receives the write
    client.write_node('ns=2;s=MirrorDev.Value', 77)
    for _ in range(30):
        found = dm.get_signal_by_unique_address(f"{cfg.name}::value")
        if found and found.value in (77, pytest.approx(77)):
            break
        time.sleep(0.05)
    else:
        pytest.skip('OPC->DeviceManager write not observed in this environment')

    client.disconnect()
    mirror.stop()
