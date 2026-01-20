import re
import logging
from typing import List

logger = logging.getLogger(__name__)


class ScriptTagManager:
    """Manage tokenized tag placeholders inside user scripts.

    Token format: {{TAG:Device::Address[#n]}}
    Provides resolving tokens to current unique addresses and helpers for insertion.
    """
    TOKEN_RE = re.compile(r"\{\{TAG:([^\}]+)\}\}")

    def __init__(self, device_manager_core):
        self._dm = device_manager_core
        self._choices = {}
        # load persisted choices from file alongside device config
        try:
            cfg = getattr(self._dm, 'config_path', 'devices.json')
            import os, json
            self._choices_path = os.path.join(os.path.dirname(os.path.abspath(cfg)), 'token_choices.json')
            if os.path.exists(self._choices_path):
                with open(self._choices_path, 'r') as f:
                    self._choices = json.load(f) or {}
        except Exception:
            self._choices = {}

    def make_token(self, unique_address: str) -> str:
        return f"{{{{TAG:{unique_address}}}}}"

    def get_choice(self, token_inner: str):
        return self._choices.get(token_inner)

    def set_choice(self, token_inner: str, unique_address: str):
        try:
            self._choices[token_inner] = unique_address
            import json, os
            with open(self._choices_path, 'w') as f:
                json.dump(self._choices, f, indent=2)
        except Exception:
            logger.exception('Failed to persist token choice')

    def get_candidates(self, token_inner: str):
        """Return list of candidate unique addresses matching the token's address portion."""
        try:
            # If token_inner resolves directly, return that
            sig = None
            try:
                sig = self._dm.get_signal_by_unique_address(token_inner)
            except Exception:
                sig = None
            if sig and getattr(sig, 'unique_address', None):
                return [sig.unique_address]

            device_old, addr = (None, None)
            try:
                device_old, addr = self._dm.parse_unique_address(token_inner)
            except Exception:
                pass
            if not addr:
                return []
            candidates = []
            for u in self._dm.list_unique_addresses():
                part = u.split('::', 1)[1]
                part_base = part.split('#', 1)[0]
                if part_base == addr:
                    candidates.append(u)
            return candidates
        except Exception:
            return []

    def extract_tokens(self, code: str) -> List[str]:
        return [m.group(1) for m in self.TOKEN_RE.finditer(code)]

    def resolve_code(self, code: str) -> str:
        """Replace tokens with the current canonical unique address (quoted where appropriate).

        Replacement strategy:
        - If the device manager can resolve the token exactly via `get_signal_by_unique_address`, use that signal's `unique_address`.
        - Otherwise, parse the address portion and search all known unique addresses for the same address part.
        - If multiple candidates exist, prefer one that keeps the original device name when possible.
        """
        if not code:
            return code

        def _replace(match):
            inner = match.group(1)
            try:
                # Exact match first
                sig = None
                try:
                    sig = self._dm.get_signal_by_unique_address(inner)
                except Exception:
                    sig = None

                if sig and getattr(sig, 'unique_address', None):
                    resolved = sig.unique_address
                    return repr(resolved)

                # Parse and search by address portion
                try:
                    device_old, addr = self._dm.parse_unique_address(inner)
                except Exception:
                    device_old, addr = (None, None)

                if not addr:
                    return repr(inner)

                candidates = []
                try:
                    for u in self._dm.list_unique_addresses():
                        # Compare base address portion ignoring any #n suffix
                        part = u.split('::', 1)[1]
                        part_base = part.split('#', 1)[0]
                        if part_base == addr:
                            candidates.append(u)
                except Exception:
                    candidates = []

                if not candidates:
                    return repr(inner)

                # Prefer candidate with same device_old if possible
                if device_old:
                    for c in candidates:
                        if c.startswith(f"{device_old}::"):
                            return repr(c)

                # Otherwise if single candidate, pick it
                if len(candidates) == 1:
                    return repr(candidates[0])

                # Ambiguous: return the first candidate
                return repr(candidates[0])
            except Exception as e:
                logger.debug(f"ScriptTagManager: Failed to resolve token {inner}: {e}")
                return repr(inner)

        # Replace tokens in the code with quoted unique addresses so they can be used directly
        return self.TOKEN_RE.sub(_replace, code)

    def resolve_code_interactive(self, code: str, chooser) -> str:
        """Resolve tokens, but when multiple candidates are found call `chooser(token, candidates)`
        which should return the chosen unique_address (string) or None to skip/keep original.
        """
        if not code:
            return code

        def _replace(match):
            inner = match.group(1)
            try:
                sig = None
                try:
                    sig = self._dm.get_signal_by_unique_address(inner)
                except Exception:
                    sig = None

                if sig and getattr(sig, 'unique_address', None):
                    resolved = sig.unique_address
                    return repr(resolved)

                device_old, addr = (None, None)
                try:
                    device_old, addr = self._dm.parse_unique_address(inner)
                except Exception:
                    pass

                if not addr:
                    return repr(inner)

                candidates = []
                try:
                    for u in self._dm.list_unique_addresses():
                        part = u.split('::', 1)[1]
                        part_base = part.split('#', 1)[0]
                        if part_base == addr:
                            candidates.append(u)
                except Exception:
                    candidates = []

                if not candidates:
                    return repr(inner)

                if len(candidates) == 1:
                    return repr(candidates[0])

                # Ambiguous: check persisted choice first
                persisted = self._choices.get(inner)
                if persisted and persisted in candidates:
                    return repr(persisted)

                # Ask chooser for selection
                if chooser:
                    try:
                        chosen = chooser(inner, candidates)
                        if chosen:
                            return repr(chosen)
                    except Exception:
                        pass

                # Fallback: pick first
                return repr(candidates[0])
            except Exception as e:
                logger.debug(f"ScriptTagManager: Failed to resolve token {inner}: {e}")
                return repr(inner)

        return self.TOKEN_RE.sub(_replace, code)

    def update_tokens(self, code: str) -> str:
        """Return code where token inner unique-addresses are updated to current canonical values,
        but tokens themselves are preserved (i.e. still in the {{TAG:...}} form).
        """
        if not code:
            return code

        def _replace(match):
            inner = match.group(1)
            try:
                # Try exact resolution first
                sig = None
                try:
                    sig = self._dm.get_signal_by_unique_address(inner)
                except Exception:
                    sig = None

                if sig and getattr(sig, 'unique_address', None):
                    return self.make_token(sig.unique_address)

                # Fall back to matching by address portion
                try:
                    device_old, addr = self._dm.parse_unique_address(inner)
                except Exception:
                    device_old, addr = (None, None)

                if not addr:
                    return match.group(0)

                candidates = []
                try:
                    for u in self._dm.list_unique_addresses():
                        part = u.split('::', 1)[1]
                        part_base = part.split('#', 1)[0]
                        if part_base == addr:
                            candidates.append(u)
                except Exception:
                    candidates = []

                if not candidates:
                    return match.group(0)

                if device_old:
                    for c in candidates:
                        if c.startswith(f"{device_old}::"):
                            return self.make_token(c)

                return self.make_token(candidates[0])
            except Exception:
                return match.group(0)

        return self.TOKEN_RE.sub(_replace, code)
