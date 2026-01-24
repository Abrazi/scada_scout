from src.protocols.iec61850 import adapter
iec61850 = adapter.iec61850


class DummyConn:
    pass


class DummyCtx:
    def __init__(self, sbo_reference=None, ctl_num=0):
        self.sbo_reference = sbo_reference
        self.ctl_num = ctl_num


def test_select_prefers_sbow_ctlnum():
    ad = adapter.IEC61850Adapter.__new__(adapter.IEC61850Adapter)
    ad.connection = DummyConn()

    # simulate reading SBOw.ctlNum returns 1, object ctlNum would return 0
    def fake_read(conn, obj_ref, fc):
        if obj_ref.endswith('.SBOw.ctlNum'):
            return (1, iec61850.IED_ERROR_OK)
        if obj_ref.endswith('.ctlNum'):
            return (0, iec61850.IED_ERROR_OK)
        return (None, 1)

    # patch the wrapper directly
    old = iec61850.IedConnection_readInt32Value
    iec61850.IedConnection_readInt32Value = fake_read
    try:
        ctx = DummyCtx(sbo_reference='IED/OBJ.SBOw', ctl_num=0)
        ad.controls = {'IED/OBJ': ctx}

        # emulate production read sequence (SBOw preferred)
        val_num, err_num = iec61850.IedConnection_readInt32Value(ad.connection, f"{ctx.sbo_reference}.ctlNum", iec61850.IEC61850_FC_ST)
        assert err_num == iec61850.IED_ERROR_OK
        ctx.ctl_num = ad._normalize_ctlnum(val_num)
        assert ctx.ctl_num == 1
    finally:
        iec61850.IedConnection_readInt32Value = old



def test_select_falls_back_to_object_ctlnum():
    ad = adapter.IEC61850Adapter.__new__(adapter.IEC61850Adapter)
    ad.connection = DummyConn()

    def fake_read(conn, obj_ref, fc):
        if obj_ref.endswith('.SBOw.ctlNum'):
            return (None, 1)
        if obj_ref.endswith('.ctlNum'):
            return (7, iec61850.IED_ERROR_OK)
        return (None, 1)

    old = iec61850.IedConnection_readInt32Value
    iec61850.IedConnection_readInt32Value = fake_read
    try:
        ctx = DummyCtx(sbo_reference='IED/OBJ.SBOw', ctl_num=0)
        val_num, err_num = iec61850.IedConnection_readInt32Value(ad.connection, f"{ctx.sbo_reference}.ctlNum", iec61850.IEC61850_FC_ST)
        assert err_num != iec61850.IED_ERROR_OK
        # fallback
        val_num, err_num = iec61850.IedConnection_readInt32Value(ad.connection, "IED/OBJ.ctlNum", iec61850.IEC61850_FC_ST)
        assert err_num == iec61850.IED_ERROR_OK
        ctx.ctl_num = ad._normalize_ctlnum(val_num)
        assert ctx.ctl_num == 7
    finally:
        iec61850.IedConnection_readInt32Value = old
