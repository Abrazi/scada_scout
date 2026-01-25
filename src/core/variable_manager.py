"""
Variable manager for script-scoped and global variables bound to device signals.

Features:
- Bind a named variable to a device::signal address
- Two update modes: on-demand and continuous (per-variable interval in ms)
- Single scheduler thread + ThreadPoolExecutor for scalable, non-blocking reads
- Owner scoping so variables created by a script are cleaned up when the
  script stops
- Thread-safe access to variable state (value, timestamp)

API (high level):
- create(owner, name, unique_address, mode, interval_ms)
- get(owner, name) -> VariableHandle
- remove(owner, name)
- stop_scope(owner) / stop_all()

Designed to integrate with DeviceManagerCore (uses its read_signal/get_signal_by_unique_address).
"""
from __future__ import annotations

import concurrent.futures
import heapq
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class _Variable:
    owner: Optional[str]
    name: str
    unique_address: str
    mode: str  # 'on_demand' | 'continuous'
    interval_ms: Optional[int]
    value: Any = None
    ts: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock)
    cancelled: bool = False


class VariableHandle:
    """Lightweight handle returned to scripts.

    Methods:
      - get() -> last known value (non-blocking)
      - read() -> force a device read (blocks the caller until read completes)
      - start()/stop() -> control continuous updates for this variable
    """
    def __init__(self, manager: "VariableManager", key: Tuple[Optional[str], str]):
        self._mgr = manager
        self._key = key

    def get(self):
        v = self._mgr._get_var(self._key)
        if not v:
            return None
        with v.lock:
            return v.value

    def read(self, timeout: Optional[float] = 1.0):
        """Force a synchronous read from the backing device. Returns the new value
        or last-known value on timeout/failure.
        """
        fut = self._mgr._schedule_immediate_read(self._key)
        try:
            sig = fut.result(timeout=timeout)
            if sig is None:
                return None
            # read_signal may return the same Signal object the DM holds; extract value
            return getattr(sig, 'value', None)
        except concurrent.futures.TimeoutError:
            logger.debug("Variable read timed out")
            # Fallback to last-known
            return self.get()

    def start(self):
        self._mgr._set_mode(self._key, 'continuous')

    def stop(self):
        self._mgr._set_mode(self._key, 'on_demand')


class VariableManager:
    """Manage variables bound to device signals with efficient scheduling.

    Implementation notes:
    - Uses a single scheduler thread that maintains a min-heap of (next_run_ts, key)
      for variables in continuous mode.
    - Uses a ThreadPoolExecutor to perform device reads so scheduler isn't blocked.
    - Variables are namespaced by `owner` (e.g. script name). Variables with
      owner=None are considered global.
    """

    def __init__(self, device_manager, max_workers: int = 6):
        self._dm = device_manager
        self._vars: Dict[Tuple[Optional[str], str], _Variable] = {}
        self._heap = []  # list of tuples (next_run_ts, owner, name)
        self._heap_entries = set()
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._stopped = False
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, name="VariableScheduler", daemon=True)
        self._scheduler_thread.start()

    # -- Public API -------------------------------------------------
    def create(self, owner: Optional[str], name: str, unique_address: str, *, mode: str = 'on_demand', interval_ms: Optional[int] = None) -> VariableHandle:
        key = (owner, name)
        with self._lock:
            if key in self._vars:
                # update config
                v = self._vars[key]
                v.unique_address = unique_address
                v.mode = mode
                v.interval_ms = interval_ms
                created = False
            else:
                v = _Variable(owner=owner, name=name, unique_address=unique_address, mode=mode, interval_ms=interval_ms)
                self._vars[key] = v
                created = True
            # If continuous, schedule next run immediately
            if mode == 'continuous' and interval_ms and interval_ms > 0:
                self._push_schedule(key, time.time())
            else:
                # ensure not in heap
                self._remove_from_heap_if_present(key)
        # Emit lifecycle event (core may bridge to UI)
        try:
            if created and hasattr(self._dm, 'emit'):
                self._dm.emit('variable_added', owner, name, unique_address)
        except Exception:
            pass
        return VariableHandle(self, key)

    def remove(self, owner: Optional[str], name: str) -> None:
        key = (owner, name)
        with self._lock:
            v = self._vars.pop(key, None)
            if v:
                v.cancelled = True
            self._remove_from_heap_if_present(key)
        try:
            if v and hasattr(self._dm, 'emit'):
                self._dm.emit('variable_removed', owner, name)
        except Exception:
            pass

    def get_handle(self, owner: Optional[str], name: str) -> Optional[VariableHandle]:
        key = (owner, name)
        with self._lock:
            if key not in self._vars:
                return None
        return VariableHandle(self, key)

    def list_vars(self, owner: Optional[str] = None):
        with self._lock:
            return [k[1] for k in self._vars.keys() if owner is None or k[0] == owner]

    def stop_scope(self, owner: Optional[str]) -> None:
        """Remove and stop all variables for a given owner (used when a script stops)."""
        with self._lock:
            keys = [k for k in self._vars.keys() if k[0] == owner]
        for k in keys:
            self.remove(k[0], k[1])

    def stop_all(self) -> None:
        with self._lock:
            keys = list(self._vars.keys())
        for k in keys:
            self.remove(k[0], k[1])
        # Stop scheduler and executor
        self._shutdown()

    # -- Internal helpers ------------------------------------------
    def _set_mode(self, key: Tuple[Optional[str], str], mode: str) -> None:
        with self._lock:
            v = self._vars.get(key)
            if not v:
                return
            v.mode = mode
            if mode == 'continuous' and v.interval_ms and v.interval_ms > 0:
                self._push_schedule(key, time.time())
            else:
                self._remove_from_heap_if_present(key)

    def _get_var(self, key: Tuple[Optional[str], str]) -> Optional[_Variable]:
        return self._vars.get(key)

    def _push_schedule(self, key: Tuple[Optional[str], str], when_ts: float) -> None:
        # next run is when_ts + interval
        v = self._vars.get(key)
        if not v or not v.interval_ms or v.interval_ms <= 0:
            return
        next_ts = when_ts + (v.interval_ms / 1000.0)
        entry = (next_ts, key)
        if key in self._heap_entries:
            # leave duplicate removal to pop time (simpler)
            pass
        else:
            heapq.heappush(self._heap, entry)
            self._heap_entries.add(key)
        self._cond.notify()

    def _remove_from_heap_if_present(self, key: Tuple[Optional[str], str]) -> None:
        # mark as removed by removing entry set; actual heap entries will be skipped when popped
        if key in self._heap_entries:
            self._heap_entries.discard(key)

    def _schedule_immediate_read(self, key: Tuple[Optional[str], str]) -> concurrent.futures.Future:
        """Schedule a single immediate read for the variable and return a Future that resolves
        to the protocol Signal (or None on failure)."""
        # Submit to executor so caller may block on the returned future
        return self._executor.submit(self._do_read_for_key, key)

    def _do_read_for_key(self, key: Tuple[Optional[str], str]):
        v = None
        with self._lock:
            v = self._vars.get(key)
            if not v or v.cancelled:
                return None
            ua = v.unique_address
        # Resolve the signal via the device manager and perform a read
        try:
            sig = self._dm.get_signal_by_unique_address(ua)
            if not sig:
                return None
            device_name, _ = self._dm.parse_unique_address(ua)
            if not device_name:
                return None
            updated = self._dm.read_signal(device_name, sig)
            # updated may be None if read queued async; return last-known in that case
            if updated is None:
                return sig
            # Update stored value
            new_val = getattr(updated, 'value', None)
            now_ts = time.time()
            changed = False
            with v.lock:
                old_val = v.value
                v.value = new_val
                v.ts = now_ts
                if old_val != new_val:
                    changed = True
            # Emit variable_updated (value changed or first-time read)
            try:
                if hasattr(self._dm, 'emit'):
                    # (owner, name, value, timestamp)
                    self._dm.emit('variable_updated', v.owner, v.name, v.value, v.ts)
            except Exception:
                pass
            return updated
        except Exception:
            logger.exception("VariableManager: read failed")
            return None

    def _scheduler_loop(self):
        with self._lock:
            while not self._stopped:
                now = time.time()
                next_ts = None
                while self._heap and (self._heap[0][0] <= now or self._heap[0][1] not in self._heap_entries):
                    ts, key = heapq.heappop(self._heap)
                    # skip stale/removed entries
                    if key not in self._heap_entries:
                        continue
                    self._heap_entries.discard(key)
                    # Dispatch read to executor
                    v = self._vars.get(key)
                    if not v or v.cancelled:
                        continue
                    # Submit read; when done, schedule next run if still continuous
                    fut = self._executor.submit(self._do_read_and_reschedule, key)

                # Compute next wake
                if self._heap:
                    next_ts = self._heap[0][0]
                    timeout = max(0.0, next_ts - time.time())
                else:
                    timeout = None
                # Wait until next schedule or until notified
                if timeout is None:
                    self._cond.wait()
                else:
                    self._cond.wait(timeout=timeout)

    def _do_read_and_reschedule(self, key: Tuple[Optional[str], str]):
        try:
            res = self._do_read_for_key(key)
        finally:
            # If variable still exists and is continuous, schedule next run
            with self._lock:
                v = self._vars.get(key)
                if v and not v.cancelled and v.mode == 'continuous' and v.interval_ms and v.interval_ms > 0:
                    self._push_schedule(key, time.time())

    def _shutdown(self):
        with self._lock:
            if self._stopped:
                return
            self._stopped = True
            self._cond.notify_all()
        try:
            self._executor.shutdown(wait=False)
        except Exception:
            logger.debug("VariableManager executor shutdown failed", exc_info=True)


# Backwards-compatible alias for other modules that may prefer this name
ScriptVariableManager = VariableManager
