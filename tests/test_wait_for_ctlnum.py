from src.protocols.iec61850 import adapter
iec61850 = adapter.iec61850


class DummyConn:
    pass


class DummyCtx:
    def __init__(self, sbo_reference=None):
        self.sbo_reference = sbo_reference
        self.ctl_num = 0


def test_wait_for_ctlnum_polls_until_available():
    ad = adapter.IEC61850Adapter.__new__(adapter.IEC61850Adapter)
    ad.connection = DummyConn()
    ad.connected = True
    class _L:
        def __enter__(self):
            return None
        def __exit__(self, *a):
            return False
    ad._lock = _L()

    # simulate readInt32Value returning (None,1) twice then returning (7, OK)
    calls = {'n': 0}

    def fake_read(conn, ref, fc):
        calls['n'] += 1
        if calls['n'] < 3:
            return (None, 1)
        return (7, iec61850.IED_ERROR_OK)

    iec61850.IedConnection_readInt32Value = fake_read

    ctx = DummyCtx(sbo_reference='IED/OBJ.Pos.SBOw')
    ok = ad._wait_for_ctlnum(ctx, 'IED/OBJ.Pos', timeout_ms=500)
    assert ok is True
    assert ctx.ctl_num == 7


def test_wait_for_ctlnum_uses_async_fallback_when_polling_fails():
    ad = adapter.IEC61850Adapter.__new__(adapter.IEC61850Adapter)
    ad.connection = DummyConn()
    ad.connected = True
    class _L:
        def __enter__(self):
            return None
        def __exit__(self, *a):
            return False
    ad._lock = _L()

    # polling always fails
    iec61850.IedConnection_readInt32Value = lambda *a, **k: (None, 1)
    iec61850.IedConnection_readObject = lambda *a, **k: None

    # fake async callback to supply ctlNum
    def fake_select_async(client, errptr, handler, user_ptr):
        class FakeAction: pass
        action = FakeAction()
        iec61850.ControlAction_getCtlNum = lambda ap: 123
        handler(1, action, 0, 0, True)
        return 1

    iec61850.ControlObjectClient_selectAsync = fake_select_async
    iec61850.ControlObjectClient_create = lambda obj_ref, conn: object()
    iec61850.ControlObjectClient_destroy = lambda c: None

    ctx = DummyCtx(sbo_reference='IED/OBJ.Pos.SBOw')
    ok = ad._wait_for_ctlnum(ctx, 'IED/OBJ.Pos', timeout_ms=300)
    assert ok is True
    assert ctx.ctl_num == 123
