"""
Testes de contrato dos snapshots de release congelados (Eixo 2 — histórico).

Complementam ``test_openapi_contract.py``: enquanto aquele congela o contrato vivo
num único snapshot, aqui verificamos os arquivos por *release* em
``docs/openapi/{slug}/{release}.json`` — a segunda testemunha do contrato,
navegável na referência e escrita por ``scripts/freeze_openapi.py``.

Garantias:

* o arquivo da release corrente existe, é OpenAPI 3.x e expõe ``/api/v1``;
* o manifesto e :func:`frozen_openapi` enxergam a release, e o dict devolvido
  bate com o arquivo em disco;
* releases inexistentes e tentativas de path traversal devolvem ``None``
  (bloqueadas pela validação de manifesto);
* ``scripts/freeze_openapi.py --check`` passa para o snapshot commitado — ou seja,
  o congelado mais recente continua idêntico ao OpenAPI enriquecido vivo;
* o OpenAPI vivo de ``/api/v1`` NÃO tem quebras vs. a release congelada mais nova
  (reaproveitando :func:`find_breaking_changes` do teste de contrato).
"""

from __future__ import annotations

import json

from app.api.openapi import DOCS_OPENAPI_DIR, frozen_openapi, openapi_for_version, release_manifest
from app.main import app
from scripts.freeze_openapi import freeze

from tests.contract.test_openapi_contract import find_breaking_changes

CURRENT_RELEASE = "1.3.0"
V1_SNAPSHOT = DOCS_OPENAPI_DIR / "v1" / f"{CURRENT_RELEASE}.json"
API_PREFIX = "/api/v1"


def test_frozen_v1_file_exists_and_is_openapi_3x() -> None:
    """O arquivo congelado da release corrente existe, é OpenAPI 3.x e expõe /api/v1."""
    assert V1_SNAPSHOT.is_file(), f"snapshot de release ausente: {V1_SNAPSHOT}"
    schema = json.loads(V1_SNAPSHOT.read_text(encoding="utf-8"))
    assert str(schema.get("openapi", "")).startswith("3."), "não é OpenAPI 3.x"
    api_paths = [p for p in schema.get("paths", {}) if p.startswith(API_PREFIX)]
    assert api_paths, "nenhum path sob /api/v1 no snapshot congelado"


def test_manifest_and_frozen_openapi_match_file() -> None:
    """O manifesto lista a release e :func:`frozen_openapi` devolve o dict do arquivo."""
    assert CURRENT_RELEASE in release_manifest("v1")
    frozen = frozen_openapi("v1", CURRENT_RELEASE)
    assert frozen is not None
    on_disk = json.loads(V1_SNAPSHOT.read_text(encoding="utf-8"))
    assert frozen == on_disk


def test_frozen_openapi_rejects_unknown_and_traversal() -> None:
    """Releases inexistentes e path traversal são bloqueados (devolvem ``None``)."""
    assert frozen_openapi("v1", "9.9.9") is None
    assert frozen_openapi("v1", "../../secret") is None
    assert frozen_openapi("v1", "../index") is None


def test_freeze_check_passes_for_committed_snapshot() -> None:
    """``freeze(check=True)`` passa: o congelado commitado bate com o OpenAPI vivo."""
    # ``build_public_openapi`` cacheia em ``app.openapi_schema``; limpa para refletir
    # o schema vivo caso outro teste no mesmo processo o tenha mutado.
    app.openapi_schema = None
    assert freeze(check=True) == 0


def test_live_v1_has_no_breaking_changes_vs_frozen_release() -> None:
    """O OpenAPI vivo de /api/v1 não quebra o contrato da release congelada mais nova."""
    frozen = frozen_openapi("v1", CURRENT_RELEASE)
    assert frozen is not None
    app.openapi_schema = None
    live = openapi_for_version(app, "v1")
    breaks = find_breaking_changes(frozen, live)
    assert not breaks, "quebras vs. release congelada:\n" + "\n".join(f"  - {b}" for b in breaks)
