"""
Validação de cobertura e integridade do snapshot da BNCC (T027, Princípio IV).

Verifica:
  1. Unicidade dos códigos de habilidade.
  2. Formato por etapa (EI/EF/EM) de cada código.
  3. Integridade referencial: competências específicas e competências gerais
     referenciadas por habilidades resolvem para entidades existentes.
  4. Contagens por etapa/componente e presença das etapas.

Saída: exit code != 0 em erros graves (duplicidade / código malformado /
referência quebrada / cobertura zero de qualquer uma das três etapas EI/EF/EM).

Uso:
    python scripts/validate_bncc_coverage.py [caminho_do_snapshot]
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("validate_bncc")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.models.bncc import (  # noqa: E402
    CODE_PATTERN_EF,
    CODE_PATTERN_EI,
    CODE_PATTERN_EM,
    is_valid_codigo,
)

DEFAULT_SNAPSHOT = ROOT / "data" / "bncc_v1.json"


def _etapa_ok(codigo: str, etapa: str) -> bool:
    if etapa == "educacao_infantil":
        return bool(CODE_PATTERN_EI.match(codigo))
    if etapa == "ensino_fundamental":
        return bool(CODE_PATTERN_EF.match(codigo))
    if etapa == "ensino_medio":
        # Aceita padrão por área e a variante oficial de Língua Portuguesa.
        return bool(CODE_PATTERN_EM.match(codigo)) or is_valid_codigo(codigo)
    return False


def validate(snapshot: dict[str, Any]) -> dict[str, list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    habs = snapshot.get("habilidades", [])
    comp_esp_codes = {
        str(c.get("codigo", "")).upper() for c in snapshot.get("competencias_especificas", [])
    }
    comp_gerais_nums = {c.get("numero") for c in snapshot.get("competencias_gerais", [])}

    # 1 + 2: unicidade e formato por etapa
    seen: set[str] = set()
    for h in habs:
        codigo = str(h.get("codigo", "")).upper()
        etapa = h.get("etapa", "")
        if not codigo:
            errors.append("Habilidade sem código.")
            continue
        if codigo in seen:
            errors.append(f"Código duplicado: {codigo}")
        seen.add(codigo)
        if not is_valid_codigo(codigo):
            errors.append(f"Código malformado: {codigo}")
        elif not _etapa_ok(codigo, etapa):
            errors.append(f"Código {codigo} não casa com a etapa '{etapa}'.")

        # 3: integridade referencial
        for cod in h.get("competencias_especificas", []) or []:
            if str(cod).upper() not in comp_esp_codes:
                errors.append(f"{codigo}: competência específica inexistente '{cod}'.")
        for num in h.get("competencias_gerais", []) or []:
            if comp_gerais_nums and num not in comp_gerais_nums:
                errors.append(f"{codigo}: competência geral inexistente '{num}'.")

    # 4: contagens/cobertura
    por_etapa: dict[str, int] = {}
    for h in habs:
        por_etapa[h.get("etapa", "?")] = por_etapa.get(h.get("etapa", "?"), 0) + 1
    logger.info("Cobertura por etapa: %s", por_etapa)

    if por_etapa.get("ensino_fundamental", 0) == 0:
        errors.append("Cobertura zero para ensino_fundamental (SC-001).")
    if por_etapa.get("ensino_medio", 0) == 0:
        errors.append("Cobertura zero para ensino_medio (SC-001).")
    if por_etapa.get("educacao_infantil", 0) == 0:
        errors.append("Cobertura zero para educacao_infantil (SC-001, três etapas).")

    if len(snapshot.get("competencias_gerais", [])) != 10:
        errors.append(
            "Competências gerais devem ser exatamente 10 "
            f"(encontradas {len(snapshot.get('competencias_gerais', []))})."
        )

    # 5: Complemento de Computação (par oficial `CO`; eixo em EI/EF, ausente no EM)
    VALID_EIXOS = {"pensamento_computacional", "mundo_digital", "cultura_digital"}
    computacao = [h for h in habs if str(h.get("codigo", "")).upper()[4:6] == "CO"]
    if not computacao:
        errors.append("Cobertura zero para o Complemento de Computação (habilidades `CO`).")
    for h in computacao:
        codigo = str(h.get("codigo", "")).upper()
        etapa = h.get("etapa", "")
        if h.get("componente") != "computacao" or h.get("area_conhecimento") != "computacao":
            errors.append(f"{codigo}: Computação deve ter área/componente 'computacao'.")
        eixo = h.get("eixo")
        if etapa == "ensino_medio":
            if eixo is not None:
                errors.append(
                    f"{codigo}: Ensino Médio de Computação não deve ter eixo (tem '{eixo}')."
                )
        else:  # EI/EF
            if eixo not in VALID_EIXOS:
                errors.append(f"{codigo}: eixo de Computação ausente/ inválido ('{eixo}').")
    logger.info("Habilidades de Computação: %d", len(computacao))

    # 6: Relações navegáveis (FR-005) — coleções e integridade dos objetos.
    unidades = snapshot.get("unidades_tematicas", [])
    objetos = snapshot.get("objetos_conhecimento", [])
    campos = snapshot.get("campos_experiencia", [])
    comp_esp = snapshot.get("competencias_especificas", [])
    if not comp_esp:
        errors.append("Catálogo de competências específicas vazio (FR-005).")
    if not unidades:
        errors.append("Coleção de unidades temáticas vazia (FR-005).")
    if not objetos:
        errors.append("Coleção de objetos de conhecimento vazia (FR-005).")
    if not campos:
        errors.append("Campos de experiência (Educação Infantil) vazios (FR-005).")
    # Integridade: objeto referenciado por habilidade resolve para o catálogo.
    objeto_nomes = {str(o.get("nome", "")) for o in objetos}
    for h in habs:
        for nome in h.get("objetos_conhecimento", []) or []:
            if nome not in objeto_nomes:
                errors.append(f"{h.get('codigo')}: objeto de conhecimento inexistente '{nome}'.")
                break
    logger.info(
        "Relações: %d competências específicas, %d unidades temáticas, %d objetos, %d campos.",
        len(comp_esp),
        len(unidades),
        len(objetos),
        len(campos),
    )

    return {"errors": errors, "warnings": warnings}


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SNAPSHOT
    if not path.exists():
        logger.error("Snapshot não encontrado: %s", path)
        return 2

    snapshot = json.loads(path.read_text(encoding="utf-8"))
    result = validate(snapshot)

    for w in result["warnings"]:
        logger.warning(w)
    for e in result["errors"][:50]:
        logger.error(e)

    if result["errors"]:
        logger.error(
            "Validação FALHOU: %d erro(s), %d aviso(s).",
            len(result["errors"]),
            len(result["warnings"]),
        )
        return 1

    logger.info("Validação OK: 0 erros, %d aviso(s).", len(result["warnings"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
