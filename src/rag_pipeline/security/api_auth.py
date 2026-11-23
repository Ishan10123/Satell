from collections import defaultdict, deque
import hmac
import threading
import time


def validate_api_token(provided: str, expected: str) -> bool:
    return bool(provided) and hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


class ApiRateLimiter:
    """Small in-process fixed-window limiter for the single-user loopback API."""

    def __init__(self, requests_per_minute: int = 30, window_seconds: float = 60.0) -> None:
        if requests_per_minute < 1 or window_seconds <= 0:
            raise ValueError("Rate limit and window must be positive.")
        self.requests_per_minute = requests_per_minute
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        with self._lock:
            events = self._requests[key]
            while events and events[0] <= current - self.window_seconds:
                events.popleft()
            if len(events) >= self.requests_per_minute:
                return False
            events.append(current)
            return True
