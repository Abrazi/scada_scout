from src.protocols.iec61850 import adapter
iec61850 = adapter.iec61850


class DummyConn:
    pass


class DummySignal:
    def __init__(self, address):
        self.address = address


def test_send_command_aborts_when_ctlnum_unavailable():
    ad = adapter.IEC61850Adapter.__new__(adapter.IEC61850Adapter)
    ad.connection = DummyConn()
    ad.connected = True
    class _L:
        def __enter__(self):
            return None
        def __exit__(self, *a):
            return False
    ad._lock = _L()
    ad.event_logger = type('L', (), {'info': lambda *a, **k: None, 'debug': lambda *a, **k: None, 'error': lambda *a, **k: None, 'transaction': lambda *a, **k: None, 'warning': lambda *a, **k: None})()
    ad.controls = {}

    sig = DummySignal('IED/OBJ.Pos.stVal')

    # make select succeed but ctlNum reads always fail
    iec61850.ControlObjectClient_create = lambda ref, conn: object()
    iec61850.ControlObjectClient_getControlModel = lambda c: 2
    iec61850.ControlObjectClient_select = lambda c: True
    iec61850.ControlObjectClient_destroy = lambda c: None

    iec61850.IedConnection_readInt32Value = lambda *a, **k: (None, 1)
    iec61850.IedConnection_readObject = lambda *a, **k: None

    # ensure send_command will run the SBO sequence
    from src.protocols.iec61850.control_models import ControlObjectRuntime
    ctx = ControlObjectRuntime(object_reference='IED/OBJ.Pos')
    ctx.update_from_ctl_model_int(2)  # SBO_NORMAL
    ctx.ctl_num = 0
    ctx.sbo_reference = 'IED/OBJ.Pos.SBOw'
    ad.controls['IED/OBJ.Pos'] = ctx

    ok = ad.send_command(sig, True, params={'sbo_timeout': 10})
    assert ok is False
    assert getattr(ad, '_last_control_error', None) is not None
