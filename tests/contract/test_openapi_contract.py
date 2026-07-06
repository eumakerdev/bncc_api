"""
Teste de regressão de contrato OpenAPI (Princípio I — Contrato Primeiro).

A superfície pública sob ``/api/v1`` é um contrato consumido por sistemas de
terceiros. Mudanças incompatíveis dentro de uma versão publicada são PROIBIDAS
(ver ``.specify/memory/constitution.md`` §I): remoção/renomeação de campo,
alteração de tipo, novo campo obrigatório em request, remoção de valor de enum,
remoção de path/endpoint. Adições retrocompatíveis (novo endpoint, novo campo
opcional, novo valor de enum) são PERMITIDAS.

Como funciona
-------------
- ``openapi_snapshot.json`` (versionado ao lado deste arquivo) é o "contrato
  publicado" congelado: um dump determinístico de ``app.openapi()``.
- Em cada execução comparamos o OpenAPI gerado em runtime contra o snapshot e
  FALHAMOS apenas em mudanças *incompatíveis*, restritas ao contrato público
  (paths ``/api/v1`` e os schemas alcançáveis a partir deles). Rotas SSR do
  portal (``/portal``) não fazem parte do contrato de API e são ignoradas.
- Adições retrocompatíveis não quebram o teste; elas são detectadas e emitidas
  como aviso (``warnings.warn``), visível com ``pytest -W`` / ``-s``.

Atualizar o snapshot (somente para mudanças INTENCIONAIS e retrocompatíveis)
---------------------------------------------------------------------------
Uma mudança incompatível NÃO deve ser "resolvida" atualizando o snapshot — ela
exige uma nova versão de caminho (``/api/v2``, Princípio I). Para congelar
adições retrocompatíveis, regenere o snapshot:

    # bash
    UPDATE_OPENAPI_SNAPSHOT=1 pytest tests/contract/test_openapi_contract.py

    # PowerShell
    $env:UPDATE_OPENAPI_SNAPSHOT=1; pytest tests/contract/test_openapi_contract.py

Depois, revise o diff do JSON e faça o commit junto com a mudança de código.
"""

from __future__ import annotations

import json
import os
import warnings
from pathlib import Path
from typing import Any

import pytest
from app.main import app

SNAPSHOT_PATH = Path(__file__).parent / "openapi_snapshot.json"
API_PREFIX = "/api/v1"
HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}


# --------------------------------------------------------------------------- #
# Geração / carga do schema                                                   #
# --------------------------------------------------------------------------- #
def _current_schema() -> dict[str, Any]:
    """OpenAPI gerado pelo app em runtime (fonte da verdade viva)."""
    # ``app.openapi()`` cacheia em ``app.openapi_schema``; limpamos para refletir
    # qualquer mutação em testes que rodem no mesmo processo.
    app.openapi_schema = None
    return app.openapi()


def _dump(schema: dict[str, Any]) -> str:
    """Serialização determinística (chaves ordenadas) para diffs legíveis."""
    return json.dumps(schema, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def _write_snapshot(schema: dict[str, Any]) -> None:
    SNAPSHOT_PATH.write_text(_dump(schema), encoding="utf-8")


def _load_snapshot() -> dict[str, Any]:
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Utilitários estruturais (sem dependências externas — Princípio VII/YAGNI)   #
# --------------------------------------------------------------------------- #
def _collect_refs(node: Any, acc: set[str]) -> None:
    """Coleta nomes de schemas referenciados (``#/components/schemas/X``)."""
    if isinstance(node, dict):
        for key, value in node.items():
            if (
                key == "$ref"
                and isinstance(value, str)
                and value.startswith("#/components/schemas/")
            ):
                acc.add(value.rsplit("/", 1)[-1])
            else:
                _collect_refs(value, acc)
    elif isinstance(node, list):
        for item in node:
            _collect_refs(item, acc)


def _reachable_schemas(schema: dict[str, Any], prefix: str) -> set[str]:
    """Fecho transitivo dos schemas alcançáveis a partir das operações ``prefix``.

    Restringe a verificação ao contrato público: schemas usados apenas por rotas
    fora de ``/api/v1`` (ex.: formulários do portal) não são enforçados aqui.
    """
    all_schemas = schema.get("components", {}).get("schemas", {})
    seed: set[str] = set()
    for path, ops in schema.get("paths", {}).items():
        if path.startswith(prefix):
            _collect_refs(ops, seed)

    result: set[str] = set()
    stack = list(seed)
    while stack:
        name = stack.pop()
        if name in result:
            continue
        result.add(name)
        if name in all_schemas:
            sub: set[str] = set()
            _collect_refs(all_schemas[name], sub)
            stack.extend(sub - result)
    return result


def _type_sig(node: Any) -> str:
    """Descritor estável do *formato* de um campo (ignora título/descrição/default).

    Captura ``type``/``format``/``$ref`` e recursivamente ``items``/``anyOf``/
    ``allOf``/``additionalProperties``. ``enum`` é tratado à parte.
    """
    if not isinstance(node, dict):
        return json.dumps({"const": node}, sort_keys=True)
    sig: dict[str, Any] = {}
    for key in ("type", "format", "$ref"):
        if key in node:
            sig[key] = node[key]
    if "items" in node:
        sig["items"] = _type_sig(node["items"])
    for combiner in ("anyOf", "oneOf", "allOf"):
        if combiner in node and isinstance(node[combiner], list):
            sig[combiner] = sorted(_type_sig(sub) for sub in node[combiner])
    extra = node.get("additionalProperties")
    if isinstance(extra, dict):
        sig["additionalProperties"] = _type_sig(extra)
    return json.dumps(sig, sort_keys=True)


def _enum_values(node: Any) -> set[Any] | None:
    """Conjunto de valores de enum de um nó (ou ``None`` se não for enum)."""
    if isinstance(node, dict) and isinstance(node.get("enum"), list):
        try:
            return set(node["enum"])
        except TypeError:  # valores não-hasháveis: normaliza via JSON
            return {json.dumps(v, sort_keys=True) for v in node["enum"]}
    return None


def _compare_schema(name: str, old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    """Detecta quebras de contrato num schema componente."""
    out: list[str] = []
    old_props = old.get("properties", {})
    new_props = new.get("properties", {})

    for prop, old_p in sorted(old_props.items()):
        if prop not in new_props:
            out.append(
                f"CAMPO REMOVIDO: '{name}.{prop}' não existe mais no schema atual "
                f"(clientes que leem esse campo quebram)."
            )
            continue
        new_p = new_props[prop]
        old_sig, new_sig = _type_sig(old_p), _type_sig(new_p)
        if old_sig != new_sig:
            out.append(f"TIPO ALTERADO: '{name}.{prop}' mudou de {old_sig} para {new_sig}.")
        old_enum = _enum_values(old_p)
        if old_enum is not None:
            removed = old_enum - (_enum_values(new_p) or set())
            if removed:
                out.append(
                    f"VALOR DE ENUM REMOVIDO: '{name}.{prop}' perdeu {sorted(map(str, removed))}."
                )

    # Enum declarado no próprio schema (Enums do Pydantic viram schema com 'enum').
    old_enum = _enum_values(old)
    if old_enum is not None:
        removed = old_enum - (_enum_values(new) or set())
        if removed:
            out.append(
                f"VALOR DE ENUM REMOVIDO: schema '{name}' perdeu {sorted(map(str, removed))}."
            )

    # Novo campo obrigatório (quebra requests que não o enviam).
    old_required = set(old.get("required", []))
    new_required = set(new.get("required", []))
    for prop in sorted(new_required - old_required):
        out.append(
            f"CAMPO OBRIGATÓRIO NOVO/ALTERADO: '{name}.{prop}' passou a ser obrigatório "
            f"(quebra requests existentes)."
        )
    return out


def find_breaking_changes(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    """Lista as quebras de contrato de ``old`` (publicado) para ``new`` (atual).

    Restrito ao contrato público ``/api/v1`` e aos schemas por ele alcançáveis.
    Uma lista vazia significa "sem mudança incompatível".
    """
    breaks: list[str] = []
    old_paths = old.get("paths", {})
    new_paths = new.get("paths", {})

    # 1. Paths e métodos sob /api/v1.
    for path, old_ops in sorted(old_paths.items()):
        if not path.startswith(API_PREFIX):
            continue
        if path not in new_paths:
            breaks.append(f"PATH REMOVIDO: '{path}' não existe mais.")
            continue
        new_ops = new_paths[path]
        for method in sorted(old_ops):
            if method.lower() not in HTTP_METHODS:
                continue
            if method not in new_ops:
                breaks.append(f"MÉTODO REMOVIDO: '{method.upper()} {path}' não existe mais.")

    # 2. Schemas alcançáveis a partir de /api/v1.
    old_schemas = old.get("components", {}).get("schemas", {})
    new_schemas = new.get("components", {}).get("schemas", {})
    for name in sorted(_reachable_schemas(old, API_PREFIX)):
        old_s = old_schemas.get(name)
        if old_s is None:
            continue
        new_s = new_schemas.get(name)
        if new_s is None:
            breaks.append(f"SCHEMA REMOVIDO: '{name}' era referenciado pelo contrato e sumiu.")
            continue
        breaks.extend(_compare_schema(name, old_s, new_s))

    return breaks


def find_additions(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    """Adições retrocompatíveis (informativo — NÃO falham o teste)."""
    additions: list[str] = []
    old_paths, new_paths = old.get("paths", {}), new.get("paths", {})
    for path, ops in sorted(new_paths.items()):
        if not path.startswith(API_PREFIX):
            continue
        if path not in old_paths:
            additions.append(f"novo path '{path}'")
        else:
            for method in sorted(ops):
                if method.lower() in HTTP_METHODS and method not in old_paths[path]:
                    additions.append(f"novo método '{method.upper()} {path}'")
    return additions


# --------------------------------------------------------------------------- #
# Testes                                                                       #
# --------------------------------------------------------------------------- #
def test_openapi_snapshot_regeneration_hook():
    """Regenera o snapshot quando ``UPDATE_OPENAPI_SNAPSHOT=1`` (mudança intencional)."""
    if os.environ.get("UPDATE_OPENAPI_SNAPSHOT") != "1":
        pytest.skip("defina UPDATE_OPENAPI_SNAPSHOT=1 para regenerar o snapshot")
    _write_snapshot(_current_schema())
    pytest.skip(f"snapshot regenerado em {SNAPSHOT_PATH.name}; revise o diff e commite")


def test_openapi_contract_has_no_breaking_changes():
    """O contrato ``/api/v1`` atual NÃO pode conter quebras vs. o snapshot publicado."""
    assert SNAPSHOT_PATH.exists(), (
        f"Snapshot de contrato ausente ({SNAPSHOT_PATH}). "
        "Gere-o com UPDATE_OPENAPI_SNAPSHOT=1 e commite."
    )
    snapshot = _load_snapshot()
    current = _current_schema()

    additions = find_additions(snapshot, current)
    if additions:  # informativo apenas — permitido pelo Princípio I.
        warnings.warn(
            "Adições retrocompatíveis ao contrato /api/v1: "
            + "; ".join(additions)
            + ". Regenere o snapshot (UPDATE_OPENAPI_SNAPSHOT=1) para congelá-las.",
            stacklevel=2,
        )

    breaks = find_breaking_changes(snapshot, current)
    assert not breaks, (
        "QUEBRA DE CONTRATO OpenAPI detectada em /api/v1 (Princípio I — mudanças "
        "incompatíveis são PROIBIDAS dentro de uma versão publicada):\n"
        + "\n".join(f"  - {b}" for b in breaks)
        + "\n\nSe a mudança for INTENCIONAL, ela exige uma NOVA versão de caminho "
        "(/api/v2) com depreciação da anterior — NÃO atualize o snapshot para "
        "'consertar' esta falha. Se, e somente se, a mudança for de fato "
        "retrocompatível (o comparador é conservador), regenere o snapshot com "
        "UPDATE_OPENAPI_SNAPSHOT=1 e revise o diff."
    )


def test_openapi_smoke_public_surface():
    """Sanidade: o OpenAPI existe, é 3.x e expõe a superfície pública esperada."""
    schema = _current_schema()
    assert str(schema.get("openapi", "")).startswith("3.")
    api_paths = [p for p in schema.get("paths", {}) if p.startswith(API_PREFIX)]
    assert api_paths, "nenhum path sob /api/v1 no OpenAPI"
    # Todo endpoint público deve declarar respostas tipadas (Princípio I/III).
    for path in api_paths:
        for method, op in schema["paths"][path].items():
            if method.lower() in HTTP_METHODS:
                assert op.get("responses"), f"{method.upper()} {path} sem 'responses'"
