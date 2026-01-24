from src.protocols.iec61850 import adapter
iec61850 = adapter.iec61850


class DummyConn:
    pass


class DummySignal:
    def __init__(self, address):
        self.address = address


def test_read_ctlnum_from_sbo_structure():
    ad = adapter.IEC61850Adapter.__new__(adapter.IEC61850Adapter)
    ad.connection = DummyConn()
    ad.connected = True
    class _L:
        def __enter__(self):
            return None
        def __exit__(self, *a):
            return False
    ad._lock = _L()
    ad.event_logger = None
    ad.controls = {}

    sig = DummySignal("IED/OBJ.Pos.stVal")
    # prepare context
    from src.protocols.iec61850.control_models import ControlObjectRuntime
    ctx = ControlObjectRuntime(object_reference='IED/OBJ.Pos')
    ctx.sbo_reference = 'IED/OBJ.Pos.SBOw'
    ctx.ctl_num = 0
    ad.controls['IED/OBJ.Pos'] = ctx

    # Make direct int read fail
    iec61850.IedConnection_readInt32Value = lambda conn, ref, fc: (None, 1)
    # ensure getDataDirectory doesn't call into native code
    iec61850.IedConnection_getDataDirectory = lambda conn, ref: ([],)

    # Simulate reading the SBOw structure and extracting element 3
    fake_mms = object()
    iec61850.IedConnection_readObject = lambda conn, ref, fc: fake_mms
    iec61850.MmsValue_getElement = lambda m, idx: ('elem' if idx == 3 else None)
    iec61850.MmsValue_toInt32 = lambda e: 99
    iec61850.MmsValue_delete = lambda m: None

    # Call the internal logic by invoking select and letting it attempt the reads
    # Patch ControlObjectClient_create/getControlModel/select to short-circuit to the ctlNum-read section
    iec61850.ControlObjectClient_create = lambda obj_ref, conn: object()
    iec61850.ControlObjectClient_getControlModel = lambda c: 2
    iec61850.ControlObjectClient_select = lambda c: True
    iec61850.ControlObjectClient_destroy = lambda c: None
    ok = ad.select(sig, value=None, params=None)
    assert ok is True
    key = ad._get_control_object_reference(sig.address)
    assert ad.controls[key].ctl_num == 99
