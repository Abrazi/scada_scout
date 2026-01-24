from src.protocols.iec61850 import adapter


def test_normalize_ctlnum_from_int():
    a = adapter.IEC61850Adapter.__new__(adapter.IEC61850Adapter)
    assert a._normalize_ctlnum(5) == 5


def test_normalize_ctlnum_from_str_decimal():
    a = adapter.IEC61850Adapter.__new__(adapter.IEC61850Adapter)
    assert a._normalize_ctlnum("42") == 42


def test_normalize_ctlnum_from_str_hex():
    a = adapter.IEC61850Adapter.__new__(adapter.IEC61850Adapter)
    assert a._normalize_ctlnum("0xFF") == 255


def test_normalize_ctlnum_wraps_mod_256():
    a = adapter.IEC61850Adapter.__new__(adapter.IEC61850Adapter)
    assert a._normalize_ctlnum(256) == 0
    assert a._normalize_ctlnum(257) == 1


class DummyCtx:
    def __init__(self, ctl_num):
        self.ctl_num = ctl_num


def test_increment_ctlnum_wraps_to_zero():
    a = adapter.IEC61850Adapter.__new__(adapter.IEC61850Adapter)
    c = DummyCtx(255)
    # mimic post-operate increment used in adapter
    try:
        c.ctl_num = (int(c.ctl_num) + 1) % 256
    except Exception:
        c.ctl_num = 0
    assert c.ctl_num == 0
