import hashlib
import json
import threading
import time
from collections import OrderedDict
from typing import Any


class ResponseCache:
    def __init__(self, max_entries: int = 256, ttl_seconds: int = 900):
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._items: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            created_at, value = item
            if time.time() - created_at > self.ttl_seconds:
                self._items.pop(key, None)
                return None
            self._items.move_to_end(key)
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._items[key] = (time.time(), value)
            self._items.move_to_end(key)
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)


def make_cache_key(*parts: Any) -> str:
    payload = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
