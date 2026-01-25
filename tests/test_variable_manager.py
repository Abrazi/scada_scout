import time
import threading

from src.core.variable_manager import VariableManager
from src.core.script_runtime import UserScriptManager, run_script_once


class _FakeSignal:
    def __init__(self, value=None):
        self.value = value


class _FakeDM:
    def __init__(self):
        self._sig = _FakeSignal(None)

    def get_signal_by_unique_address(self, ua):
        return self._sig

    def parse_unique_address(self, ua):
        # return (device, addr)
        return ("DEV", ua)

    def read_signal(self, device_name, sig):
        # simulate synchronous read returning an updated signal object
        return sig


def test_on_demand_variable_read():
    dm = _FakeDM()
    vm = VariableManager(dm)

    # create variable and force a read
    h = vm.create(None, 'v1', 'DEV::a', mode='on_demand')
    assert h.get() is None

    # simulate device update
    dm._sig.value = 42
    val = h.read(timeout=0.5)
    assert val == 42
    assert h.get() == 42

    vm.stop_all()


def test_continuous_variable_updates():
    dm = _FakeDM()
    counter = {'v': 0}

    # override read_signal to increment value
    def read_sig(device_name, sig):
        counter['v'] += 1
        sig.value = counter['v']
        return sig

    dm.read_signal = read_sig

    vm = VariableManager(dm, max_workers=2)
    h = vm.create(None, 'ctr', 'DEV::c', mode='continuous', interval_ms=50)

    # allow some updates to occur
    time.sleep(0.22)
    val1 = h.get()
    assert val1 is not None and val1 >= 3

    # stop and ensure no more updates after a short wait
    h.stop()
    v_after_stop = val1
    time.sleep(0.18)
    assert h.get() == v_after_stop

    vm.stop_all()


def test_script_scope_cleanup_on_stop():
    # Integration (no Qt): fake DeviceManager with a VariableManager so UserScriptManager
    # can exercise bind/unbind lifecycle without pulling GUI dependencies.
    class FakeDM:
        def __init__(self):
            from src.core.variable_manager import VariableManager
            self._variable_manager = VariableManager(self)
            self._sig = _FakeSignal(0)
        def get_signal_by_unique_address(self, ua):
            return self._sig
        def parse_unique_address(self, ua):
            return ("DEV", ua)
        def read_signal(self, device_name, sig):
            sig.value = 1
            return sig
        # forwarders used by ScriptContext
        def create_variable(self, owner, name, unique_address, **kw):
            return self._variable_manager.create(owner, name, unique_address, **kw)
        def list_variables(self, owner=None):
            return self._variable_manager.list_vars(owner)

    dm = FakeDM()
    usm = UserScriptManager(dm)

    code = """def tick(ctx):
    v = ctx.bind_variable('x', 'DEV::a', mode='continuous', interval_ms=30)
    # let variable spin for a short while
    for _ in range(3):
        if ctx.should_stop():
            return
        ctx.sleep(0.05)
"""

    usm.start_script('s1', code, interval=0.05)
    time.sleep(0.18)
    # variable should exist
    handles = dm.list_variables('s1')
    assert 'x' in handles

    usm.stop_script('s1')
    time.sleep(0.05)
    handles = dm.list_variables('s1')
    assert 'x' not in handles

    usm.stop_all()
    dm._variable_manager.stop_all()


def test_core_variable_events():
    # Exercise VariableManager's event emissions without importing Qt-dependent core.
    events = {'added': None, 'updated': None}

    class FakeCore:
        def __init__(self):
            self._sig = _FakeSignal(None)
        def emit(self, *args, **kwargs):
            # record the last emitted event for simple assertions
            events_key = args[0] if args else None
            events[events_key] = args[1:]
        def get_signal_by_unique_address(self, ua):
            return self._sig
        def parse_unique_address(self, ua):
            return ('DEV', ua)
        def read_signal(self, device_name, sig):
            sig.value = 77
            return sig

    fc = FakeCore()
    from src.core.variable_manager import VariableManager
    vm = VariableManager(fc)

    # Create variable and ensure 'variable_added' emitted via FakeCore.emit
    h = vm.create(None, 'evt_var', 'DEV::a', mode='on_demand')
    assert events.get('variable_added') is not None

    # Force a synchronous read and ensure variable_updated was emitted
    v = h.read(timeout=0.5)
    assert v == 77
    # allow small scheduling window
    time.sleep(0.02)
    assert events.get('variable_updated') is not None

    vm.stop_all()
