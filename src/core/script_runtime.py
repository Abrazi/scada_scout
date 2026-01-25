import logging
import threading
import time
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)


class ScriptContext:
    """Context passed to user scripts for tag access.

    New: supports script-scoped variables bound to device signals via the
    DeviceManagerCore's VariableManager. Variables may be 'on_demand' or
    'continuous' with per-variable interval (ms).
    """
    def __init__(self, device_manager_core, event_logger=None, owner: Optional[str] = None):
        self._dm = device_manager_core
        self._event_logger = event_logger
        # owner is the script name or None for top-level one-shot runs
        self._owner = owner
        self._stop_event = None

    def get(self, tag_address: str, default=None):
        """Get last known value for a tag by unique address (Device::Address)."""
        sig = self._dm.get_signal_by_unique_address(tag_address)
        if not sig:
            return default
        return getattr(sig, 'value', default)

    def read(self, tag_address: str):
        """Force a read for a tag and return value (best effort)."""
        sig = self._dm.get_signal_by_unique_address(tag_address)
        if not sig:
            return None
        device_name, _ = self._dm.parse_unique_address(tag_address)
        if not device_name:
            return None
        updated = self._dm.read_signal(device_name, sig)
        if updated is None:
            # Async read queued; return last known value
            return getattr(sig, 'value', None)
        return getattr(updated, 'value', None)

    # ----------------- Variable binding API for user scripts -------------
    def bind_variable(self, name: str, tag_address: str, mode: str = 'on_demand', interval_ms: Optional[int] = None):
        """Bind a named variable to a device signal.

        - name: user-visible variable name (scoped to this script)
        - tag_address: unique address (Device::addr...)
        - mode: 'on_demand' | 'continuous'
        - interval_ms: required for continuous mode

        Returns: VariableHandle-like object with .get(), .read(), .start(), .stop()
        """
        if not hasattr(self._dm, '_variable_manager'):
            raise RuntimeError('VariableManager not available')
        # Validate tag exists (best-effort)
        sig = self._dm.get_signal_by_unique_address(tag_address)
        if not sig:
            # still allow binding so user can create variable before device model exists
            pass
        return self._dm.create_variable(self._owner, name, tag_address, mode=mode, interval_ms=interval_ms)

    def unbind_variable(self, name: str):
        if not hasattr(self._dm, '_variable_manager'):
            return
        return self._dm.remove_variable(self._owner, name)

    def var(self, name: str):
        """Return a handle for a previously-created variable (or None)."""
        if not hasattr(self._dm, '_variable_manager'):
            return None
        return self._dm.get_variable_handle(self._owner, name)

    def list_variables(self):
        if not hasattr(self._dm, '_variable_manager'):
            return []
        return self._dm.list_variables(self._owner)

    # ---------------------------------------------------------------------

    def set(self, tag_address: str, value) -> bool:
        """Write a value to a tag by unique address.

        Convenience: if `tag_address` refers to a control DO (e.g. 'DEV::IED/LD/CSWI1.Pos')
        resolve to the control leaf (ctlVal/Oper) and perform a proper control
        (SELECT/OPERATE) via `send_command` so the user only needs to supply the DO
        and the desired value.
        """
        sig = self._dm.get_signal_by_unique_address(tag_address)
        if not sig:
            # Try to resolve DO -> control leaf and use send_command for controls
            device_name, addr = self._dm.parse_unique_address(tag_address)
            if not device_name or not addr:
                return False

            # Try the same candidate resolution as send_command
            candidates = [
                f"{addr}.Oper.ctlVal",
                f"{addr}.Oper",
                f"{addr}.ctlVal",
                f"{addr}.SBOw.ctlVal",
                f"{addr}.SBO.ctlVal",
            ]
            for c in candidates:
                sig = self._dm.get_signal_by_unique_address(f"{device_name}::{c}")
                if sig:
                    break

            if not sig:
                # not a control DO we can resolve
                return False

            # resolved a control leaf — use send_command to perform safe control
            return self.send_command(f"{device_name}::{addr}", value)

        device_name, _ = self._dm.parse_unique_address(tag_address)
        if not device_name:
            return False
        return self._dm.write_signal(device_name, sig, value)

    def send_command(self, tag_address: str, value, params: dict = None) -> bool:
        """
        Send an IEC 61850 control command (supports SBO workflow automatically).

        Convenience improvements:
        - Accepts either a DA leaf address (e.g. "...Pos.ctlVal") *or* the DO address
          (e.g. "...Pos"). When given a DO the runtime will resolve the best writable
          control DA (Oper.ctlVal, ctlVal, SBOw/SBO) so the user doesn't need to know
          the ctlMode/attribute names.
        - Minimal call: ctx.send_command('DEV::IED/LD/CSWI1.Pos', True)
        - Advanced: pass `params` to override behavior. Supported keys:
            - sbo_timeout (int ms)
            - originator_id (str)
            - originator_cat (int)
            - force_direct (bool)  -- skip SELECT and call OPERATE
            - force_sbo (bool)     -- force SELECT+OPERATE even if ctlModel suggests direct
            - ctl_num (int)        -- override ctlNum used for Operate
            - ctl_attr (str)       -- explicit attribute to target (e.g. 'Oper.ctlVal')

        Backwards-compatible: existing behavior and the UI control window are NOT changed.

        Returns:
            bool
        """
        # Fast-path: exact match
        sig = self._dm.get_signal_by_unique_address(tag_address)

        # If not exact, try to resolve a control leaf from a DO-style address
        if not sig:
            device_name, addr = self._dm.parse_unique_address(tag_address)
            if not device_name or not addr:
                return False

            # Candidate suffixes in preferred order
            candidates = [
                f"{addr}.Oper.ctlVal",
                f"{addr}.Oper",
                f"{addr}.ctlVal",
                f"{addr}.SBOw.ctlVal",
                f"{addr}.SBO.ctlVal",
            ]

            # If user passed a leaf that was missing a device prefix, try a fuzzy search
            for c in candidates:
                sig = self._dm.get_signal_by_unique_address(f"{device_name}::{c}")
                if sig:
                    break

            # Last-resort: scan device addresses for the first match that looks like a control
            if not sig:
                for u in self._dm.list_unique_addresses(device_name):
                    # match DO prefix and prefer ctlVal/Oper
                    if u.startswith(f"{device_name}::{addr}") and ("ctlVal" in u or ".Oper" in u or "SBO" in u):
                        sig = self._dm.get_signal_by_unique_address(u)
                        if sig:
                            break

        if not sig:
            return False

        device_name, _ = self._dm.parse_unique_address(sig.unique_address if hasattr(sig, 'unique_address') else tag_address)
        if not device_name:
            return False

        adapter = self._dm.get_protocol(device_name)
        if not adapter:
            return False

        # If adapter doesn't support send_command, fall back to write_signal
        if not hasattr(adapter, 'send_command'):
            return self._dm.write_signal(device_name, sig, value)

        # Pass through params (advanced) — runtime already resolves DO -> ctl leaf
        return adapter.send_command(sig, value, params)

    def list_tags(self, device_name: Optional[str] = None):
        """List unique tag addresses (optionally for a single device)."""
        return self._dm.list_unique_addresses(device_name=device_name)

    def sleep(self, seconds: float):
        time.sleep(seconds)

    def log(self, level: str, message: str):
        """Log to EventLogger if available, else standard logger."""
        if self._event_logger:
            try:
                if level.lower() == "info":
                    self._event_logger.info("UserScript", message)
                    return
                if level.lower() == "warning":
                    self._event_logger.warning("UserScript", message)
                    return
                if level.lower() == "error":
                    self._event_logger.error("UserScript", message)
                    return
            except Exception:
                pass
        logger.info(message)

    def should_stop(self) -> bool:
        """Return True when the hosting script runner has requested stop."""
        try:
            return bool(self._stop_event and self._stop_event.is_set())
        except Exception:
            return False


class UserScriptManager:
    """Runs user-supplied Python scripts in background threads."""
    def __init__(self, device_manager_core, event_logger=None):
        self._dm = device_manager_core
        self._event_logger = event_logger
        self._scripts: Dict[str, Dict[str, object]] = {}
        self._lock = threading.Lock()

    def start_script(self, name: str, code: str, interval: float = 0.5) -> None:
        with self._lock:
            if name in self._scripts:
                raise ValueError(f"Script '{name}' already running")

            stop_event = threading.Event()
            # Pass the script name as owner so any variables created are scoped and
            # can be cleaned up automatically when the script stops.
            ctx = ScriptContext(self._dm, self._event_logger, owner=name)
            # Give the context a handle to the stop event so user code can poll
            ctx._stop_event = stop_event
            # Resolve any token placeholders before compiling
            try:
                tag_mgr = getattr(self._dm, '_script_tag_manager', None)
                if tag_mgr:
                    code_to_compile = tag_mgr.resolve_code(code)
                else:
                    code_to_compile = code
            except Exception:
                code_to_compile = code

            compiled = self._compile_script(code_to_compile, ctx)

            mode, obj = compiled

            def _runner():
                self._log("info", f"Script '{name}' started")
                try:
                    if mode == "tick":
                        # Call the tick function repeatedly at the given interval
                        while not stop_event.is_set():
                            try:
                                obj(ctx)
                            except Exception as exc:
                                self._log("error", f"Script '{name}' error: {exc}")
                            if interval > 0:
                                time.sleep(interval)
                    elif mode == "loop":
                        # The function manages its own loop; call it once and let it run
                        try:
                            obj(ctx)
                        except Exception as exc:
                            self._log("error", f"Script '{name}' error: {exc}")
                    else:
                        # Raw script: execute the code in a fresh namespace (may block if user uses while True)
                        sandbox = {"ctx": ctx}
                        try:
                            exec(obj, sandbox, sandbox)
                        except Exception as exc:
                            self._log("error", f"Script '{name}' error: {exc}")
                finally:
                    self._log("info", f"Script '{name}' stopped")

            thread = threading.Thread(target=_runner, daemon=True)
            self._scripts[name] = {
                "thread": thread,
                "stop": stop_event,
                "code": code,
                "interval": interval,
                "last_resolved": code_to_compile,
            }
            thread.start()

    def restart_scripts_with_token_resolution(self, tag_mgr) -> None:
        """Check running scripts for token resolution changes and restart them if needed.

        `tag_mgr` should implement `resolve_code(code)` which returns the code with tokens
        replaced by current canonical values. We compare resolved strings; if different,
        stop and restart the script so the new addresses take effect.
        """
        if not tag_mgr:
            return

        # Snapshot current scripts to avoid mutation during iteration
        with self._lock:
            entries = {name: dict(meta) for name, meta in self._scripts.items()}

        for name, meta in entries.items():
            try:
                orig_code = meta.get("code")
                if not orig_code:
                    continue
                new_resolved = tag_mgr.resolve_code(orig_code)
                last_resolved = meta.get("last_resolved")
                if last_resolved is None:
                    last_resolved = new_resolved
                if new_resolved != last_resolved:
                    interval = meta.get("interval", 0.5)
                    # Restart: stop then start with same original source (start_script will resolve again)
                    self.stop_script(name)
                    time.sleep(0.05)
                    self.start_script(name, orig_code, interval)
            except Exception:
                # Log and continue
                logger.exception(f"Failed to consider restarting script '{name}'")

    def stop_script(self, name: str) -> None:
        with self._lock:
            entry = self._scripts.get(name)
            if not entry:
                return
            entry["stop"].set()
            self._scripts.pop(name, None)
        # Best-effort: remove any variables created by this script
        try:
            if getattr(self._dm, '_variable_manager', None):
                self._dm._variable_manager.stop_scope(name)
        except Exception:
            pass

    def stop_all(self):
        with self._lock:
            for entry in self._scripts.values():
                entry["stop"].set()
            self._scripts.clear()
        try:
            if getattr(self._dm, '_variable_manager', None):
                self._dm._variable_manager.stop_all()
        except Exception:
            pass

    def list_scripts(self):
        with self._lock:
            return list(self._scripts.keys())

    def _compile_script(self, code: str, ctx: ScriptContext):
        # For compatibility we allow three styles:
        # 1) tick(ctx) - called repeatedly by the runner
        # 2) loop(ctx) or main(ctx) - called once and expected to manage its own loop
        # 3) raw top-level script - no function defined; executed with `ctx` present
        # This function returns a tuple (mode, obj) where mode is 'tick'|'loop'|'script'
        sandbox: Dict[str, object] = {"ctx": ctx}
        exec(compile(code, '<user_script>', 'exec'), sandbox, sandbox)
        if "tick" in sandbox and callable(sandbox.get("tick")):
            return ("tick", sandbox.get("tick"))
        if "loop" in sandbox and callable(sandbox.get("loop")):
            return ("loop", sandbox.get("loop"))
        if "main" in sandbox and callable(sandbox.get("main")):
            return ("loop", sandbox.get("main"))
        # No callable found; return raw source so it can be exec'd inside the runner thread
        return ("script", code)

    def _log(self, level: str, message: str):
        if self._event_logger:
            try:
                if level == "info":
                    self._event_logger.info("UserScript", message)
                    return
                if level == "warning":
                    self._event_logger.warning("UserScript", message)
                    return
                if level == "error":
                    self._event_logger.error("UserScript", message)
                    return
            except Exception:
                pass
        logger.info(message)


def run_script_once(code: str, device_manager_core, event_logger=None) -> None:
    ctx = ScriptContext(device_manager_core, event_logger)
    # Resolve any tag tokens if a tag manager is available
    try:
        tag_mgr = getattr(device_manager_core, '_script_tag_manager', None)
        if tag_mgr:
            code = tag_mgr.resolve_code(code)
    except Exception:
        pass

    sandbox: Dict[str, object] = {"ctx": ctx}
    # Execute top-level code (this allows users to use if/for/while directly at top-level)
    exec(compile(code, '<user_script_once>', 'exec'), sandbox, sandbox)
    # If the script defined a callable entry, call it (pass ctx if it accepts args)
    func = sandbox.get("tick") or sandbox.get("loop") or sandbox.get("main")
    if callable(func):
        try:
            func(ctx)
        except TypeError:
            # In case the user defined a function that doesn't take ctx, call without args
            func()
