import os
import time
import json
import tempfile
import shutil

import pytest

sys_path_added = False
try:
    import sys
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
        sys_path_added = True
except Exception:
    pass

from src.core.script_tag_manager import ScriptTagManager


class DummyDM:
    def __init__(self, addresses):
        self._addresses = addresses
        self.config_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'devices.json')

    def list_unique_addresses(self):
        return list(self._addresses)

    def get_signal_by_unique_address(self, ua):
        # Fake signal object
        if ua in self._addresses:
            class Sig:
                def __init__(self, ua):
                    self.unique_address = ua
            return Sig(ua)
        return None

    def parse_unique_address(self, ua):
        if '::' in ua:
            d, a = ua.split('::', 1)
            if '#' in a:
                a = a.split('#', 1)[0]
            return d, a
        return None, None


def test_token_extract_and_candidates(tmp_path, monkeypatch):
    addresses = [
        'A::tag1',
        'B::tag1',
        'A::tag2#1',
    ]
    dm = DummyDM(addresses)
    mgr = ScriptTagManager(dm)

    code = "print({{TAG:A::tag1}}); print({{TAG:A::tag2}})"
    tokens = mgr.extract_tokens(code)
    assert 'A::tag1' in tokens
    assert 'A::tag2' in tokens

    c1 = mgr.get_candidates('A::tag1')
    # Exact unique-address match returns the exact signal only
    assert c1 == ['A::tag1']

    c2 = mgr.get_candidates('A::tag2')
    assert any(u.startswith('A::tag2') for u in c2)


def test_persist_choice(tmp_path, monkeypatch):
    addresses = ['A::foo', 'B::foo']
    dm = DummyDM(addresses)
    # place choices file in temp folder by pointing config_path
    dm.config_path = os.path.join(str(tmp_path), 'devices.json')
    mgr = ScriptTagManager(dm)

    token_inner = 'X::foo'
    # ensure no choice
    assert mgr.get_choice(token_inner) is None
    mgr.set_choice(token_inner, 'B::foo')
    # new manager should load persisted choice
    mgr2 = ScriptTagManager(dm)
    assert mgr2.get_choice(token_inner) == 'B::foo'
