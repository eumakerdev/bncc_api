"""
Limitadores por bucket das API keys (instância única — módulo global).

Vivem fora de ``app/core/deps.py`` para quebrar o ciclo de importação
deps ↔ usage_service (ambos precisavam dos limitadores, mas usage_service era
importado tardiamente por deps). Qualquer módulo importa os limitadores daqui.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.ratelimit import SlidingWindowLimiter

deterministic_limiter = SlidingWindowLimiter(
    max_requests=settings.RATE_LIMIT_DETERMINISTIC_PER_MIN,
    window_seconds=60,
    burst=settings.RATE_LIMIT_DETERMINISTIC_BURST,
)
ai_limiter = SlidingWindowLimiter(max_requests=settings.RATE_LIMIT_AI_PER_MIN, window_seconds=60)
