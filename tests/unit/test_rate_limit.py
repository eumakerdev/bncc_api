"""
Testes unitários do SlidingWindowLimiter (T038).

Cotas (FR-010/FR-010a): determinístico 60/min + burst 10 (⇒ 70 permitidas por
janela) e IA 20/min. Verifica bloqueio com ``retry_after`` positivo e reset de
janela.
"""

from __future__ import annotations

from app.core.ratelimit import SlidingWindowLimiter


def test_deterministic_allows_60_plus_burst_10_then_blocks():
    limiter = SlidingWindowLimiter(max_requests=60, window_seconds=60, burst=10)
    key = "deterministic:acct"

    for i in range(70):
        allowed, retry_after = limiter.check(key)
        assert allowed is True, f"chamada {i} deveria ser permitida"
        assert retry_after == 0

    allowed, retry_after = limiter.check(key)
    assert allowed is False
    assert retry_after > 0


def test_ai_bucket_20_per_min():
    limiter = SlidingWindowLimiter(max_requests=20, window_seconds=60)
    key = "ai:acct"

    for _ in range(20):
        allowed, _ = limiter.check(key)
        assert allowed is True

    allowed, retry_after = limiter.check(key)
    assert allowed is False
    assert retry_after > 0


def test_current_reflects_count_without_recording():
    limiter = SlidingWindowLimiter(max_requests=20, window_seconds=60)
    key = "ai:acct"
    assert limiter.current(key) == 0

    for _ in range(5):
        limiter.check(key)
    # current() não registra: chamadas repetidas mantêm a contagem.
    assert limiter.current(key) == 5
    assert limiter.current(key) == 5


def test_reset_clears_window():
    limiter = SlidingWindowLimiter(max_requests=20, window_seconds=60)
    key = "ai:acct"

    for _ in range(20):
        limiter.check(key)
    allowed, _ = limiter.check(key)
    assert allowed is False

    limiter.reset(key)
    assert limiter.current(key) == 0
    allowed, retry_after = limiter.check(key)
    assert allowed is True
    assert retry_after == 0


def test_window_reset_via_short_window():
    """Com janela curta, os eventos expiram e novas chamadas são liberadas."""
    import time

    limiter = SlidingWindowLimiter(max_requests=2, window_seconds=1)
    key = "k"
    assert limiter.check(key)[0] is True
    assert limiter.check(key)[0] is True
    assert limiter.check(key)[0] is False

    time.sleep(1.1)
    assert limiter.check(key)[0] is True
