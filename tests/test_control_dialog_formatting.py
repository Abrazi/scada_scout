from src.ui.dialogs.control_dialog import ControlDialog


class DummySignal:
    def __init__(self, value, address="CSWI1.Pos.stVal", name="stVal", enum_map=None):
        self.value = value
        self.address = address
        self.name = name
        if enum_map is not None:
            self.enum_map = enum_map


def test_format_numeric_enum_from_int():
    cd = ControlDialog.__new__(ControlDialog)
    sig = DummySignal(3, address="CSWI1.Pos.stVal", name="stVal")
    assert cd._format_status_value(sig) == "0x3 (3) bad"


def test_format_hex_string():
    cd = ControlDialog.__new__(ControlDialog)
    sig = DummySignal("0x02")
    assert cd._format_status_value(sig) == "0x2 (2) closed"


def test_format_boolean_and_plain_number():
    cd = ControlDialog.__new__(ControlDialog)
    assert cd._format_status_value(DummySignal(True)) == "0x1 (1)"
    assert cd._format_status_value(DummySignal(5)) == "0x5 (5)"


def test_format_non_numeric_falls_back():
    cd = ControlDialog.__new__(ControlDialog)
    sig = DummySignal("UNKNOWN")
    assert cd._format_status_value(sig) == "UNKNOWN"
