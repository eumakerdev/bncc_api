"""
Auditoria de fidelidade de texto (T029, achado G3, SC-002).

Confere que o texto servido pela API corresponde exatamente ao texto persistido
no snapshot versionado, para uma amostra de códigos oficiais das três etapas
(EI/EF/EM), e que não há caracteres de substituição (perda de acento na extração).
Códigos ausentes na amostra são ignorados via `pytest.skip` (a extração de PDF é
best-effort — ver relatório de qualidade).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.core.config import settings
from app.main import app
from app.services.bncc_service import BNCCDataService

SNAPSHOT_PATH = Path(settings.BNCC_DATA_PATH)

# Amostra de códigos oficiais para auditoria de fidelidade (EI + EF + EM).
# Os códigos de EI foram verificados no snapshot regenerado (extração por coluna de
# faixa etária a partir do BNCC_20dez_site.pdf normalizado via pikepdf).
SAMPLE_CODES = [
    "EI01EO01",
    "EI02TS01",
    "EI03ET08",
    "EF05MA07",
    "EF15LP01",
    "EF67EF01",
    "EF69AR01",
    "EM13MAT101",
    "EM13CNT101",
    "EM13LP01",
]


@pytest.fixture(scope="module")
def snapshot():
    if not SNAPSHOT_PATH.exists():
        pytest.skip(f"Snapshot {SNAPSHOT_PATH} ausente.")
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def real_service(snapshot, override_api_key_auth):
    """Injeta o serviço carregado a partir do snapshot REAL (não seedado)."""
    from app.core.deps import get_bncc_service

    service = BNCCDataService(data=snapshot)
    app.dependency_overrides[get_bncc_service] = lambda: service
    yield service
    app.dependency_overrides.pop(get_bncc_service, None)


@pytest.mark.parametrize("codigo", SAMPLE_CODES)
def test_texto_servido_igual_ao_snapshot(client, real_service, snapshot, codigo):
    by_code = {h["codigo"]: h for h in snapshot["habilidades"]}
    if codigo not in by_code:
        pytest.skip(f"Código {codigo} não presente no snapshot (extração best-effort).")

    resp = client.get(f"/api/v1/habilidades/{codigo}")
    assert resp.status_code == 200, resp.text
    served = resp.json()["descricao"]

    # Fidelidade: texto servido == texto do snapshot (correspondência exata).
    assert served == by_code[codigo]["descricao"]
    # Nenhum caractere de substituição Unicode (perda de acento na extração).
    assert "�" not in served
    assert len(served) > 10


def test_amostra_tem_cobertura_minima(snapshot):
    """Ao menos parte da amostra oficial deve estar presente (sanidade da extração)."""
    by_code = {h["codigo"] for h in snapshot["habilidades"]}
    presentes = [c for c in SAMPLE_CODES if c in by_code]
    assert len(presentes) >= 3, f"Amostra insuficiente no snapshot: {presentes}"
