"""
Regressão de sanitização de logs (Princípio V — entrada hostil na fronteira).

Valores controlados pelo usuário não podem forjar linhas/formatar o log
(CRLF injection, sequências de controle). Os pontos de log afetados usam
``repr()``; este teste falha se a sanitização for removida.
"""

from __future__ import annotations

import logging

import pytest
from app.services.bncc_service import BNCCDataService


@pytest.mark.asyncio
async def test_log_de_habilidade_invalida_escapa_controle_do_usuario(caplog):
    """Código com quebra de linha não pode forjar uma segunda linha no log."""
    # Snapshot corrompido de propósito: o código casa com a entrada do usuário
    # (após upper) e a validação Pydantic falha, disparando o warning.
    codigo_malicioso = "EF99XX\n[forjado] INFO: invasao"
    service = BNCCDataService(
        {"habilidades": [{"codigo": codigo_malicioso.upper(), "descricao": ""}]}
    )

    with caplog.at_level(logging.WARNING):
        resultado = await service.get_habilidade_by_codigo(codigo_malicioso)

    assert resultado is None
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings, "a habilidade inválida deveria gerar um warning"
    # O input do usuário não pode aparecer cru na mensagem (CRLF forjaria uma
    # segunda linha de log); com repr() a quebra vem escapada. O restante do
    # texto (ex.: ValidationError do Pydantic) é interno, não input do usuário.
    assert all("EF99XX\n" not in msg for msg in warnings)
    assert any("EF99XX\\n" in msg for msg in warnings)
    # Controle positivo: a mensagem ainda identifica o código.
    assert any("EF99XX" in msg for msg in warnings)
