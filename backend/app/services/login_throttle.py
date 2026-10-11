import math
import threading
import time
from collections import deque
from collections.abc import Callable

from fastapi import Request

TOO_MANY_DETAIL = "Too many login attempts. Try again later."


def client_key(request: Request) -> str:
    """Who is logging in: CF-Connecting-IP, else last X-Forwarded-For hop, else peer."""
    cf = request.headers.get("cf-connecting-ip", "").strip()
    if cf:
        return cf
    forwarded = request.headers.get("x-forwarded-for", "")
    last_hop = forwarded.rsplit(",", 1)[-1].strip()
    if last_hop:
        return last_hop
    return request.client.host if request.client else "unknown"


class LoginThrottle:
    """In-process failed-login limiter: per client plus a global ceiling."""

    def __init__(
        self,
        max_failures: int,
        window_seconds: int,
        global_max_failures: int,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._max = max_failures
        self._window = window_seconds
        self._global_max = global_max_failures
        self._clock = clock
        self._clients: dict[str, deque[float]] = {}
        self._global: deque[float] = deque()
        self._lock = threading.Lock()

    def _prune(self, stamps: deque[float], now: float) -> None:
        while stamps and stamps[0] <= now - self._window:
            stamps.popleft()

    def _retry_after(self, stamps: deque[float], now: float) -> int:
        return max(1, math.ceil(stamps[0] + self._window - now))

    def retry_after(self, key: str) -> int | None:
        """Seconds to wait if this client may not try now, else None."""
        with self._lock:
            now = self._clock()
            self._prune(self._global, now)
            waits = []
            if len(self._global) >= self._global_max:
                waits.append(self._retry_after(self._global, now))
            stamps = self._clients.get(key)
            if stamps is not None:
                self._prune(stamps, now)
                if not stamps:
                    del self._clients[key]
                elif len(stamps) >= self._max:
                    waits.append(self._retry_after(stamps, now))
            return max(waits) if waits else None

    def record_failure(self, key: str) -> None:
        with self._lock:
            now = self._clock()
            self._clients.setdefault(key, deque()).append(now)
            self._global.append(now)

    def record_success(self, key: str) -> None:
        with self._lock:
            self._clients.pop(key, None)
