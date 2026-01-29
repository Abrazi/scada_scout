import os
import socket
import time
import pytest

from src.protocols.iec61850 import iec61850_wrapper as iec61850

HOST = os.getenv("IEC61850_INTEGRATION_HOST", "172.16.11.18")
PORT = int(os.getenv("IEC61850_INTEGRATION_PORT", "102"))
OBJECT = os.getenv("IEC61850_INTEGRATION_OBJECT")
ALLOW = os.getenv("IEC61850_INTEGRATION_ALLOW", "0")  # must be "1" to actually operate

pytestmark = pytest.mark.integration


def _can_connect(host, port, timeout=2.0):
    try:
        s = socket.create_connection((host, port), timeout)
        s.close()
        return True
    except Exception:
        return False


@pytest.mark.skipif(OBJECT is None, reason="Set IEC61850_INTEGRATION_OBJECT to full control object (e.g. IED/LD/CSWI1.Pos)")
@pytest.mark.skipif(not _can_connect(HOST, PORT), reason="Target IED not reachable")
def test_sbo_toggle_roundtrip():
    """Integration test: SELECT (SBO) + OPERATE toggle against a live IED.

    Safety: this test will only run if environment variable
    IEC61850_INTEGRATION_ALLOW=1 is set by the operator.
    """
    if ALLOW != "1":
        pytest.skip("Integration allowed only when IEC61850_INTEGRATION_ALLOW=1")

    conn = iec61850.IedConnection_create()
    err = iec61850.IedConnection_connect(conn, HOST, PORT)
    assert err == iec61850.IED_ERROR_OK, f"Could not connect to {HOST}:{PORT} (err={err})"

    raw_obj = OBJECT.rstrip('/')
    # Normalize object reference for ControlObjectClient_create and stVal reads
    # Accept full control attribute paths like ...Oper.ctlVal or ...ctlVal
    if raw_obj.endswith(".Oper.ctlVal"):
        obj = raw_obj[: -len(".Oper.ctlVal")]
    elif raw_obj.endswith(".ctlVal"):
        obj = raw_obj[: -len(".ctlVal")]
    else:
        obj = raw_obj

    # read current stVal
    try:
        cur_bool, errb = iec61850.IedConnection_readBooleanValue(conn, f"{obj}.stVal", iec61850.IEC61850_FC_ST)
        if errb == iec61850.IED_ERROR_OK:
            cur = bool(cur_bool)
        else:
            cur = None
    except Exception:
        cur = None

    if cur is None:
        # try int
        val, erri = iec61850.IedConnection_readInt32Value(conn, f"{obj}.stVal", iec61850.IEC61850_FC_ST)
        if erri == iec61850.IED_ERROR_OK:
            cur = int(val)
        else:
            # If reading stVal fails, assume it's 0 and proceed
            print(f"Warning: Could not read stVal (error {erri}), assuming current value is 0")
            cur = 0

    # compute toggle (and ensure we can restore)
    # Assume boolean for CSWI1.Pos
    cur = bool(cur)
    target = not cur

    # create client
    client = iec61850.ControlObjectClient_create(obj, conn)
    assert client, "ControlObjectClient_create failed"

    try:
        ctl_model = iec61850.ControlObjectClient_getControlModel(client)
        print(f"Control model: {ctl_model}")

        # SELECT
        # For SBO enhanced (model 4), prefer selectWithValue
        ok = False
        if ctl_model == 4:
            mms_sel = iec61850.MmsValue_newBoolean(target) if isinstance(target, bool) else iec61850.MmsValue_newInt32(int(target))
            try:
                ok = iec61850.ControlObjectClient_selectWithValue(client, mms_sel)
            finally:
                try:
                    iec61850.MmsValue_delete(mms_sel)
                except Exception:
                    pass
        if not ok:
            ok = iec61850.ControlObjectClient_select(client)
        assert ok, "SELECT failed"

        # allow IED to publish ctlNum
        time.sleep(0.3)

        # prefer SBOw.ctlNum -> object.ctlNum
        sbo_ref = f"{obj}.SBOw"
        ctlnum = None
        try:
            v, e = iec61850.IedConnection_readInt32Value(conn, f"{sbo_ref}.ctlNum", iec61850.IEC61850_FC_ST)
            if e == iec61850.IED_ERROR_OK:
                ctlnum = int(v) % 256
        except Exception:
            pass
        if ctlnum is None:
            v, e = iec61850.IedConnection_readInt32Value(conn, f"{obj}.ctlNum", iec61850.IEC61850_FC_ST)
            assert e == iec61850.IED_ERROR_OK
            ctlnum = int(v) % 256

        # set ctlNum on client
        iec61850.ControlObjectClient_setCtlNum(client, int(ctlnum))

        # OPERATE
        mms2 = iec61850.MmsValue_newBoolean(target) if isinstance(target, bool) else iec61850.MmsValue_newInt32(int(target))
        try:
            ok2 = iec61850.ControlObjectClient_operate(client, mms2, 0)
        finally:
            iec61850.MmsValue_delete(mms2)
        assert ok2, "OPERATE failed"

        # verify stVal toggled
        time.sleep(0.5)
        try:
            newb, errb = iec61850.IedConnection_readBooleanValue(conn, f"{obj}.stVal", iec61850.IEC61850_FC_ST)
            if errb == iec61850.IED_ERROR_OK:
                new = bool(newb)
            else:
                newv, errv = iec61850.IedConnection_readInt32Value(conn, f"{obj}.stVal", iec61850.IEC61850_FC_ST)
                assert errv == iec61850.IED_ERROR_OK
                new = int(newv)
        except Exception:
            pytest.fail("Could not read stVal after OPERATE")

        assert new == target, f"stVal did not toggle (expected={target}, got={new})"

    finally:
        # best-effort restore
        try:
            # cancel any selection
            iec61850.ControlObjectClient_cancel(client)
        except Exception:
            pass
        try:
            iec61850.ControlObjectClient_destroy(client)
        except Exception:
            pass
        iec61850.IedConnection_close(conn)
        iec61850.IedConnection_destroy(conn)

    # If we changed the device, restore original value
    if new != cur:
        # Reconnect quickly and restore original value
        conn2 = iec61850.IedConnection_create()
        err2 = iec61850.IedClientError()
        iec61850.IedConnection_connect(conn2, err2, HOST, PORT)
        if err2.value == 0:
            client2 = iec61850.ControlObjectClient_create(obj, conn2)
            if client2:
                try:
                    # attempt direct operate to restore
                    m = iec61850.MmsValue_newBoolean(cur) if isinstance(cur, bool) else iec61850.MmsValue_newInt32(int(cur))
                    try:
                        iec61850.ControlObjectClient_operate(client2, m, 0)
                    finally:
                        iec61850.MmsValue_delete(m)
                finally:
                    try:
                        iec61850.ControlObjectClient_destroy(client2)
                    except Exception:
                        pass
            iec61850.IedConnection_close(conn2)
            iec61850.IedConnection_destroy(conn2)

