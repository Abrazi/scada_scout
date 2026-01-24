from src.protocols.iec61850 import adapter
iec61850 = adapter.iec61850


class DummyConn:
    pass


class DummySignal:
    def __init__(self, address, name="stVal", signal_type=None):
        self.address = address
        self.name = name
        self.signal_type = signal_type


def test_select_async_capture_ctlnum():
    ad = adapter.IEC61850Adapter.__new__(adapter.IEC61850Adapter)
    ad.connection = DummyConn()
    ad.connected = True
    class _L:
        def __enter__(self):
            return None
        def __exit__(self, *a):
            return False
    ad._lock = _L()
    # lightweight event_logger that prints so unit-test failures are visible
    ad.event_logger = type('L', (), {'info': lambda *a, **k: print(*a), 'debug': lambda *a, **k: print(*a), 'error': lambda *a, **k: print(*a), 'transaction': lambda *a, **k: print(*a), 'warning': lambda *a, **k: print(*a)})()
    ad.controls = {}

    object_ref = "IED/OBJ"
    sig = DummySignal(object_ref + ".Pos.stVal")

    # Make ControlObjectClient_create return a sentinel
    client = object()
    orig_create = iec61850.ControlObjectClient_create
    orig_getmodel = iec61850.ControlObjectClient_getControlModel
    orig_select = iec61850.ControlObjectClient_select
    orig_read = iec61850.IedConnection_readInt32Value
    orig_select_async = getattr(iec61850, 'ControlObjectClient_selectAsync', None)
    orig_getctl = getattr(iec61850, 'ControlAction_getCtlNum', None)

    try:
        iec61850.ControlObjectClient_create = lambda obj_ref, conn: client
        iec61850.ControlObjectClient_getControlModel = lambda c: 2
        iec61850.ControlObjectClient_select = lambda c: True
        iec61850.ControlObjectClient_setOriginator = lambda *a, **k: None
        iec61850.ControlObjectClient_destroy = lambda *a, **k: None

        # Make IedConnection_readInt32Value fail for SBO/object ctlNum
        def fake_read(conn, ref, fc):
            return (None, 1)
        iec61850.IedConnection_readInt32Value = fake_read

        # Simulate async select API: it should call the handler with a fake action ptr
        def fake_select_async(c, errptr, handler, user_ptr):
            class FakeAction: pass
            action = FakeAction()
            # patch ControlAction_getCtlNum to return 11 when called with this action
            iec61850.ControlAction_getCtlNum = lambda ap: 11
            # invoke handler (args: reqId, action_ptr, err, actionType, is_select)
            handler(1, action, 0, 0, True)
            return 1

        iec61850.ControlObjectClient_selectAsync = fake_select_async

        # Run select - expect ctx.ctl_num to be set to 11
        res = ad.select(sig, value=None, params=None)
        assert res is True
        key = ad._get_control_object_reference(sig.address)
        ctx = ad.controls.get(key)
        assert ctx is not None
        assert ctx.ctl_num == 11

    finally:
        iec61850.ControlObjectClient_create = orig_create
        iec61850.ControlObjectClient_getControlModel = orig_getmodel
        iec61850.ControlObjectClient_select = orig_select
        iec61850.IedConnection_readInt32Value = orig_read
        if orig_select_async is None:
            delattr(iec61850, 'ControlObjectClient_selectAsync')
        else:
            iec61850.ControlObjectClient_selectAsync = orig_select_async
        if orig_getctl is None:
            try:
                delattr(iec61850, 'ControlAction_getCtlNum')
            except Exception:
                pass
        else:
            iec61850.ControlAction_getCtlNum = orig_getctl


def test_selectWithValue_async_capture_ctlnum():
    ad = adapter.IEC61850Adapter.__new__(adapter.IEC61850Adapter)
    ad.connection = DummyConn()
    ad.connected = True
    class _L:
        def __enter__(self):
            return None
        def __exit__(self, *a):
            return False
    ad._lock = _L()
    # lightweight event_logger that prints so unit-test failures are visible
    ad.event_logger = type('L', (), {'info': lambda *a, **k: print(*a), 'debug': lambda *a, **k: print(*a), 'error': lambda *a, **k: print(*a), 'transaction': lambda *a, **k: print(*a), 'warning': lambda *a, **k: print(*a)})()
    ad.controls = {}

    object_ref = "IED/OBJ"
    sig = DummySignal(object_ref + ".Pos.stVal")

    client = object()
    orig_create = iec61850.ControlObjectClient_create
    orig_getmodel = iec61850.ControlObjectClient_getControlModel
    orig_selectw = getattr(iec61850, 'ControlObjectClient_selectWithValue', None)
    orig_read = iec61850.IedConnection_readInt32Value
    orig_async = getattr(iec61850, 'ControlObjectClient_selectWithValueAsync', None)
    orig_getctl = getattr(iec61850, 'ControlAction_getCtlNum', None)

    try:
        iec61850.ControlObjectClient_create = lambda obj_ref, conn: client
        iec61850.ControlObjectClient_getControlModel = lambda c: 4
        iec61850.ControlObjectClient_selectWithValue = lambda c, m: True
        iec61850.ControlObjectClient_setOriginator = lambda *a, **k: None
        iec61850.ControlObjectClient_destroy = lambda *a, **k: None        # ensure adapter will attempt async path by making _create_mms_value succeed
        ad._create_mms_value = lambda v, s: object()
        def fake_read(conn, ref, fc):
            return (None, 1)
        iec61850.IedConnection_readInt32Value = fake_read

        def fake_selectWithValue_async(c, errptr, mmsval, handler, user_ptr):
            class FakeAction: pass
            action = FakeAction()
            iec61850.ControlAction_getCtlNum = lambda ap: 42
            handler(2, action, 0, 0, True)
            return 1

        iec61850.ControlObjectClient_selectWithValueAsync = fake_selectWithValue_async

        res = ad.select(sig, value=1, params=None)
        assert res is True
        key = ad._get_control_object_reference(sig.address)
        ctx = ad.controls.get(key)
        assert ctx is not None
        assert ctx.ctl_num == 42

    finally:
        iec61850.ControlObjectClient_create = orig_create
        iec61850.ControlObjectClient_getControlModel = orig_getmodel
        if orig_selectw is None:
            try:
                delattr(iec61850, 'ControlObjectClient_selectWithValue')
            except Exception:
                pass
        else:
            iec61850.ControlObjectClient_selectWithValue = orig_selectw
        iec61850.IedConnection_readInt32Value = orig_read
        if orig_async is None:
            try:
                delattr(iec61850, 'ControlObjectClient_selectWithValueAsync')
            except Exception:
                pass
        else:
            iec61850.ControlObjectClient_selectWithValueAsync = orig_async
        if orig_getctl is None:
            try:
                delattr(iec61850, 'ControlAction_getCtlNum')
            except Exception:
                pass
        else:
            iec61850.ControlAction_getCtlNum = orig_getctl
