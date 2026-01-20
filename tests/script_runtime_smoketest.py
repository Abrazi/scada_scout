import sys
import os
import time

# Ensure workspace root is on sys.path so `import src...` works when run from tests/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.script_runtime import run_script_once, UserScriptManager


class DummyDM:
    def get_signal_by_unique_address(self, addr):
        return None

    def parse_unique_address(self, addr):
        return (None, None)

    def read_signal(self, device_name, sig):
        return None

    def write_signal(self, device_name, sig, value):
        return False

    def list_unique_addresses(self, device_name=None):
        return []


def main():
    dm = DummyDM()

    print('Running run_script_once with top-level control-flow')
    code = '''
for i in range(3):
    print('top-level loop', i)
    if i == 2:
        print('top-level done')
'''
    run_script_once(code, dm)

    print('\nTesting tick-style continuous script')
    mgr = UserScriptManager(dm)
    code_tick = '''def tick(ctx):
    print('tick-fn', flush=True)
'''
    mgr.start_script('tick_test', code_tick, interval=0.2)
    time.sleep(0.7)
    mgr.stop_script('tick_test')

    print('\nTesting loop-style script that polls ctx.should_stop()')
    code_loop = '''def loop(ctx):
    count = 0
    while count < 3 and not ctx.should_stop():
        print('loop-fn', count, flush=True)
        count += 1
        ctx.sleep(0.1)
'''
    mgr.start_script('loop_test', code_loop, interval=0)
    time.sleep(0.5)
    mgr.stop_script('loop_test')

    print('\nSMOKETEST_DONE')


if __name__ == '__main__':
    main()
