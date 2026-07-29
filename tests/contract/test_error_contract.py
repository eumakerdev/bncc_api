"""
Contrato das respostas de erro (Princípio I — o OpenAPI é a fonte da verdade).

Regressão da auditoria de produção de 2026-07-29 (achados 1 e 2): 15 das 25
operações publicadas declaravam `422 Validation Error`, mas o handler global
(`app/core/errors.py::validation_exception_handler`) converte **toda**
``RequestValidationError`` em `400` — o `422` documentado era inalcançável e um
cliente gerado a partir do schema caía no ramo genérico de erro. No caminho
inverso, o corpo trafegava `errors[]` sem estar no contrato, enquanto `timestamp`
era documentado e nunca enviado.

Estes testes travam o alinhamento nos dois sentidos: o que o schema promete e o
que a API realmente devolve.
"""

from __future__ import annotations

from typing import Any

import pytest
from app.main import app

API_PREFIX = "/api/v1"
HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
VALIDATION_REF = "#/components/schemas/ValidationErrorResponse"


def _schema() -> dict[str, Any]:
    app.openapi_schema = None
    return app.openapi()


def _public_operations(schema: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    return [
        (path, method, operation)
        for path, operations in schema.get("paths", {}).items()
        if path.startswith(API_PREFIX)
        for method, operation in operations.items()
        if method.lower() in HTTP_METHODS and isinstance(operation, dict)
    ]


# --------------------------------------------------------------------------- #
# O contrato documentado                                                       #
# --------------------------------------------------------------------------- #
def test_no_operation_declares_422() -> None:
    """Nenhuma operação pública promete um `422` que a API nunca devolve."""
    schema = _schema()
    offenders = [
        f"{method.upper()} {path}"
        for path, method, operation in _public_operations(schema)
        if "422" in operation.get("responses", {})
    ]
    assert (
        not offenders
    ), "operações declarando 422 (a API responde 400 — ver app/core/errors.py): " + ", ".join(
        offenders
    )


def test_operations_with_input_document_validation_400() -> None:
    """Toda operação que aceita parâmetros ou corpo documenta o `400` de validação."""
    schema = _schema()
    offenders: list[str] = []
    for path, method, operation in _public_operations(schema):
        if not operation.get("parameters") and not operation.get("requestBody"):
            continue
        response = operation.get("responses", {}).get("400")
        ref = (
            (response or {})
            .get("content", {})
            .get("application/json", {})
            .get("schema", {})
            .get("$ref")
        )
        if ref != VALIDATION_REF:
            offenders.append(f"{method.upper()} {path} -> {ref!r}")
    assert not offenders, "400 ausente ou com schema errado em: " + ", ".join(offenders)


def test_validation_error_response_schema_is_published() -> None:
    """`ValidationErrorResponse` existe no contrato e estende o corpo de erro padrão."""
    schemas = _schema().get("components", {}).get("schemas", {})
    assert "ValidationErrorResponse" in schemas
    assert "ValidationErrorItem" in schemas
    properties = schemas["ValidationErrorResponse"]["properties"]
    assert {"detail", "error_code", "timestamp", "errors"} <= set(properties)
    assert schemas["ValidationErrorItem"]["properties"].keys() >= {"campo", "msg"}


def test_legacy_validation_schemas_are_preserved() -> None:
    """`HTTPValidationError`/`ValidationError` seguem publicados (não remover — §I).

    Ficam órfãos depois do alinhamento, mas eram alcançáveis pelo contrato já
    publicado: removê-los seria uma quebra para quem gerou cliente a partir dele.
    """
    schemas = _schema().get("components", {}).get("schemas", {})
    assert "HTTPValidationError" in schemas
    assert "ValidationError" in schemas


# --------------------------------------------------------------------------- #
# O comportamento servido                                                      #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "url",
    [
        "/api/v1/habilidades?page=0",
        "/api/v1/habilidades?size=99999",
        "/api/v1/habilidades?etapa=ensino_superior",
        "/api/v1/competencias/gerais/abc",
    ],
)
def test_validation_error_body_matches_declared_schema(
    client, override_api_key_auth, url: str
) -> None:
    """O corpo do `400` de validação casa campo a campo com `ValidationErrorResponse`."""
    response = client.get(url)
    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "validation_error"
    assert isinstance(body["detail"], str) and body["detail"]
    assert isinstance(body["timestamp"], str) and body["timestamp"]
    assert body["errors"], "o detalhamento por campo é o que torna o 400 acionável"
    for item in body["errors"]:
        assert set(item) <= {"campo", "msg"}
        assert isinstance(item["campo"], str) and item["campo"]


def test_error_bodies_carry_documented_timestamp(client, override_api_key_auth) -> None:
    """`timestamp` é documentado no `ErrorResponse` — e agora realmente enviado."""
    from datetime import datetime

    for response in (
        client.get("/api/v1/habilidades/abc"),  # 400 levantado pelo roteador
        client.get("/api/v1/habilidades/EF99XX99"),  # 404
        client.get("/api/v1/rota-inexistente"),  # 404 genérico
    ):
        body = response.json()
        assert set(body) >= {"detail", "error_code", "timestamp"}
        # Parseável como ISO-8601 e com fuso (UTC).
        assert datetime.fromisoformat(body["timestamp"]).tzinfo is not None


def test_manual_400_has_no_field_details(client, override_api_key_auth) -> None:
    """O `400` de código malformado não tem `errors` — o schema o declara opcional."""
    body = client.get("/api/v1/habilidades/abc").json()
    assert body["error_code"] == "http_400"
    assert "errors" not in body
