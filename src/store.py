import threading
from typing import Any, Callable, Deque, Dict, Optional, Tuple, TypeVar

T = TypeVar("T")

class InMemoryKV:
    """Minimal in-memory KV store for interview practice.

    Not persistent, not distributed, and only safe within a single process.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def get(self, key: Tuple[str, str]) -> Dict[str, Any]:
        with self._lock:
            return dict(self._data.get(key, {}))

    def set(self, key: Tuple[str, str], value: Dict[str, Any]) -> None:
        with self._lock:
            self._data[key] = dict(value)

    def update(self, key: Tuple[str, str], updater: Callable[[Dict[str, Any]], Tuple[Dict[str, Any], T]]) -> T:
        # Atomic read-modify-write for a single key within one process.
        with self._lock:
            current = dict(self._data.get(key, {}))
            new_value, result = updater(current)
            self._data[key] = dict(new_value)
            return result
