"""
Rate limiting in-process com janela deslizante (FR-010 / FR-010a).

Instância única em v1 → contadores in-process são suficientes para a janela por
minuto; o teto diário durável é responsabilidade do usage_service (SQLite).
Redis é o caminho de escala (research.md §4).
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    """Limitador de janela deslizante por chave, thread-safe."""

    def __init__(self, max_requests: int, window_seconds: int = 60, burst: int = 0) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.burst = burst
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, int]:
        """
        Registra uma tentativa. Retorna (allowed, retry_after_seconds).

        retry_after_seconds só é relevante quando allowed=False.
        """
        now = time.monotonic()
        cutoff = now - self.window_seconds
        limit = self.max_requests + self.burst
        with self._lock:
            bucket = self._events[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = int(self.window_seconds - (now - bucket[0])) + 1
                return False, max(retry_after, 1)
            bucket.append(now)
            return True, 0

    def current(self, key: str) -> int:
        """Contagem atual na janela (sem registrar)."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            bucket = self._events[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            return len(bucket)

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._events.clear()
            else:
                self._events.pop(key, None)
