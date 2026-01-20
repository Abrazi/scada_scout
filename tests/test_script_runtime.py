import os
import sys
import time

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from src.core.script_runtime import run_script_once, UserScriptManager


def test_run_script_once_top_level():
    code = '''
for i in range(2):
    print('hello', i)
'''
    # Should not raise
    run_script_once(code, type('DM', (), {})())


def test_user_script_manager_tick(tmp_path):
    dm = type('DM', (), {})()
    dm.get_signal_by_unique_address = lambda x: None
    dm.parse_unique_address = lambda x: (None, None)
    dm.list_unique_addresses = lambda: []

    mgr = UserScriptManager(dm)
    outfile = tmp_path / 'tick_out.txt'
    code = f"""def tick(ctx):
    with open(r'{str(outfile)}', 'a') as f:
        f.write('x\\n')
"""

    mgr.start_script('t', code, interval=0.05)
    time.sleep(0.18)
    mgr.stop_script('t')
    # Check file has at least 2 lines
    data = outfile.read_text().strip().splitlines()
    assert len(data) >= 2
