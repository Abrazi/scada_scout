import types

from src.core.script_runtime import ScriptContext


class DummySignal:
    def __init__(self, unique_address, address):
        self.unique_address = unique_address
        self.address = address


class DummyDM:
    def __init__(self, signals, adapter):
        # signals: dict unique_address -> Signal
        self._signals = signals
        self._adapter = adapter

    def get_signal_by_unique_address(self, ua):
        return self._signals.get(ua)

    def parse_unique_address(self, ua):
        if "::" not in ua:
            return None, None
        return ua.split("::", 1)

    def list_unique_addresses(self, device_name=None):
        if device_name is None:
            return list(self._signals.keys())
        return [u for u in self._signals.keys() if u.startswith(device_name + "::")]

    def get_protocol(self, device_name):
        return self._adapter

    def write_signal(self, device_name, sig, value):
        # shouldn't be used for control in these tests
        raise RuntimeError("write_signal should not be used for control DOs")


class DummyAdapter:
    def __init__(self):
        self.called = []

    def send_command(self, sig, value, params=None):
        self.called.append((sig, value, params))
        return True


def test_send_command_resolves_do_to_ctlval():
    # user passes DO address (no .ctlVal) — runtime must resolve to existing ctlVal
    sig = DummySignal('DEV::IED/OBJ.Pos.ctlVal', 'IED/OBJ.Pos.ctlVal')
    adapter = DummyAdapter()
    dm = DummyDM({sig.unique_address: sig}, adapter)
    ctx = ScriptContext(dm)

    ok = ctx.send_command('DEV::IED/OBJ.Pos', True)
    assert ok is True
    assert len(adapter.called) == 1
    called_sig, called_val, called_params = adapter.called[0]
    assert called_sig is sig
    assert called_val is True
    assert called_params is None


def test_set_on_do_uses_send_command():
    # ctx.set should call adapter.send_command for DO-style addresses
    sig = DummySignal('DEV::IED/OBJ.Pos.Oper.ctlVal', 'IED/OBJ.Pos.Oper.ctlVal')
    adapter = DummyAdapter()
    dm = DummyDM({sig.unique_address: sig}, adapter)
    ctx = ScriptContext(dm)

    ok = ctx.set('DEV::IED/OBJ.Pos', False)
    assert ok is True
    assert len(adapter.called) == 1
    assert adapter.called[0][1] is False


def test_send_command_passes_advanced_params_through():
    sig = DummySignal('DEV::IED/OBJ.Pos.ctlVal', 'IED/OBJ.Pos.ctlVal')
    adapter = DummyAdapter()
    dm = DummyDM({sig.unique_address: sig}, adapter)
    ctx = ScriptContext(dm)

    params = {'sbo_timeout': 250, 'originator_id': 'TEST', 'force_direct': True}
    ok = ctx.send_command(sig.unique_address, True, params=params)
    assert ok is True
    assert adapter.called[0][2] == params
