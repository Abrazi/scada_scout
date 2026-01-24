from src.protocols.iec61850 import adapter


class DummyCtx:
    def __init__(self, cat=None, ident=None):
        self.originator_cat = cat
        self.originator_id = ident


def test_compute_originator_info_defaults_when_ctx_none():
    ad = adapter.IEC61850Adapter.__new__(adapter.IEC61850Adapter)
    ident, cat = ad._compute_originator_info(None)
    assert ident == "SCADA"
    assert cat == 3


def test_compute_originator_info_handles_zero_cat():
    ad = adapter.IEC61850Adapter.__new__(adapter.IEC61850Adapter)
    ctx = DummyCtx(cat=0, ident="UnitTest")
    ident, cat = ad._compute_originator_info(ctx)
    assert ident == "UnitTest"
    assert cat == 3  # normalized from 0 -> default 3


def test_compute_originator_info_respects_valid_cat_and_id():
    ad = adapter.IEC61850Adapter.__new__(adapter.IEC61850Adapter)
    ctx = DummyCtx(cat=5, ident="REMOTE1")
    ident, cat = ad._compute_originator_info(ctx)
    assert ident == "REMOTE1"
    assert cat == 5


def test_compute_originator_info_normalizes_placeholder_ident():
    ad = adapter.IEC61850Adapter.__new__(adapter.IEC61850Adapter)
    ctx = DummyCtx(cat=2, ident="ScadaScout")
    ident, cat = ad._compute_originator_info(ctx)
    assert ident == "SCADA"
    assert cat == 2
