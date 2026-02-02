import logging
import os
import shlex
import subprocess
import tempfile
import threading
import time
from typing import Dict, Optional


logger = logging.getLogger(__name__)


class IEC61131ScriptManager:
    """Basic IEC 61131 script runner with optional external runtime.

    If the environment variable SCADASCOUT_IEC61131_RUNNER is set, the runner
    will be invoked with the script file path as the last argument.

    If no runner is configured, scripts can still be started/stopped but will
    log a warning and perform no execution.
    """
    def __init__(self, event_logger=None):
        self._event_logger = event_logger
        self._scripts: Dict[str, Dict[str, object]] = {}
        self._lock = threading.Lock()

    def _get_runner(self):
        runner = os.environ.get("SCADASCOUT_IEC61131_RUNNER", "").strip()
        args = os.environ.get("SCADASCOUT_IEC61131_RUNNER_ARGS", "").strip()
        runner_args = shlex.split(args) if args else []
        return runner, runner_args

    def _run_once(self, name: str, code: str) -> bool:
        runner, runner_args = self._get_runner()
        if not runner:
            self._log("warning", f"IEC 61131 runner not configured; script '{name}' will not execute.")
            return False

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".st", mode="w", encoding="utf-8") as tmp:
                tmp.write(code or "")
                tmp_path = tmp.name

            cmd = [runner] + runner_args + [tmp_path]
            subprocess.run(cmd, check=False, timeout=30)
            return True
        except subprocess.TimeoutExpired:
            self._log("warning", f"IEC 61131 runner timeout for script '{name}'.")
            return False
        except Exception as exc:
            self._log("error", f"IEC 61131 script '{name}' failed: {exc}")
            return False
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    def run_once(self, name: str, code: str) -> None:
        self._log("info", f"IEC 61131 script '{name}' run once")
        self._run_once(name, code)

    def start_script(self, name: str, code: str, interval: float = 0.5) -> None:
        with self._lock:
            if name in self._scripts:
                raise ValueError(f"IEC 61131 script '{name}' already running")

            stop_event = threading.Event()

            def _runner():
                self._log("info", f"IEC 61131 script '{name}' started")
                warned = False
                try:
                    while not stop_event.is_set():
                        ok = self._run_once(name, code)
                        if not ok:
                            if not warned:
                                warned = True
                                # Avoid busy loop when no runtime is available
                                time.sleep(max(interval, 0.5))
                        if interval > 0:
                            time.sleep(interval)
                finally:
                    self._log("info", f"IEC 61131 script '{name}' stopped")

            thread = threading.Thread(target=_runner, daemon=True)
            self._scripts[name] = {
                "thread": thread,
                "stop": stop_event,
                "code": code,
                "interval": interval,
            }
            thread.start()

    def stop_script(self, name: str) -> None:
        with self._lock:
            entry = self._scripts.get(name)
            if not entry:
                return
            entry["stop"].set()
            self._scripts.pop(name, None)

    def stop_all(self) -> None:
        with self._lock:
            for entry in self._scripts.values():
                entry["stop"].set()
            self._scripts.clear()

    def list_scripts(self):
        with self._lock:
            return list(self._scripts.keys())

    def _log(self, level: str, message: str):
        if self._event_logger:
            try:
                if level == "info":
                    self._event_logger.info("IEC61131", message)
                    return
                if level == "warning":
                    self._event_logger.warning("IEC61131", message)
                    return
                if level == "error":
                    self._event_logger.error("IEC61131", message)
                    return
            except Exception:
                pass
        logger.info(message)