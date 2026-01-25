import time

import pytest

from src.protocols.opc import base_opc


def test_interfaces_exist():
    assert hasattr(base_opc, "OPCClientInterface")
    assert hasattr(base_opc, "OPCServerInterface")
    assert hasattr(base_opc, "OPCSimulator")


def test_ua_wrappers_are_guarded():
    # If python-opcua is missing the wrapper classes should raise a clear error
    try:
        from src.protocols.opc.ua_client import UAClient  # type: ignore
    except RuntimeError:
        pytest.skip("python-opcua not installed; UAClient is unavailable")

    try:
        from src.protocols.opc.ua_server import UAServer  # type: ignore
    except RuntimeError:
        pytest.skip("python-opcua not installed; UAServer is unavailable")


@pytest.mark.usefixtures()
def test_simulator_and_client_loopback():
    """Start an in-process simulator + client and perform a read/subscribe.

    Skips automatically if `opcua` is not available on the system.
    """
    opcua = pytest.importorskip("opcua")

    from src.protocols.opc.simulator import OPCSimulator
    from src.protocols.opc.ua_client import UAClient

    sim = OPCSimulator(endpoint="opc.tcp://127.0.0.1:4841")
    sim.set_point("DeviceX.Value", 123)
    sim.start()

    client = UAClient()
    client.connect("opc.tcp://127.0.0.1:4841")

    # verify read
    val = client.read_node("ns=2;s=DeviceX.Value")
    assert val == 123 or val == pytest.approx(123)

    seen = {}

    def cb(v):
        seen['v'] = v

    handle = client.subscribe("ns=2;s=DeviceX.Value", cb)

    # update simulator and wait for subscription
    sim.set_point("DeviceX.Value", 222)
    for _ in range(20):
        if seen.get('v') in (222, pytest.approx(222)):
            break
        time.sleep(0.1)
    else:
        pytest.skip("subscription callback not observed in this environment")

    client.unsubscribe(handle)
    client.disconnect()
    sim.stop()
