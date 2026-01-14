from typing import Callable, Dict, List, Any

class EventEmitter:
    """
    Simple event emitter implementation to replace Qt Signals in core logic.
    Thread-safe enough for our use case (callbacks run in the emitter's thread).
    """
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}

    def on(self, event_name: str, callback: Callable):
        """Register a callback for an event."""
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        self._listeners[event_name].append(callback)

    def off(self, event_name: str, callback: Callable):
        """Unregister a callback."""
        if event_name in self._listeners:
            try:
                self._listeners[event_name].remove(callback)
            except ValueError:
                pass

    def emit(self, event_name: str, *args, **kwargs):
        """Emit an event, calling all registered listeners."""
        if event_name in self._listeners:
            for callback in self._listeners[event_name]:
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    # Prevent one listener from crashing the emitter
                    print(f"Error in event listener for '{event_name}': {e}")

    def clear(self):
        """Remove all listeners."""
        self._listeners.clear()
