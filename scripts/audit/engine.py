"""
Motor determinístico de comparação da auditoria externa (Princípios IV e VII).

Sem I/O de rede: recebe a habilidade do snapshot e as testemunhas já obtidas das
fontes, normaliza (reuso de `_norm` de `reconcile_bncc_descriptions`) e mede, com
`difflib.SequenceMatcher` (stdlib, determinístico, sem dependência nova), DUAS
grandezas por fonte:

  - `cobertura`   — fração do texto do snapshot que está presente na testemunha
                    (soma dos blocos casados / tamanho do snapshot). É o SINAL DE
                    FIDELIDADE: pergunta "o texto oficial que servimos está
                    sustentado pela testemunha?". Tolera "bleed" de coluna na
                    extração da testemunha (texto EXTRA na fonte não penaliza);
  - `similaridade` — razão simétrica (informativa; cai quando a fonte tem bleed).

Classifica cada código pela COBERTURA da melhor fonte:

  - `concordante`      — há ≥1 fonte e a melhor cobertura fica ≥ limiar;
  - `divergente`       — a melhor cobertura fica < limiar (candidato a revisão);
  - `sem_fontes`       — nenhuma das fontes consultadas conhece o código.

Divergências são ACHADOS para o relatório, não erros de execução. A decisão de
corrigir o snapshot é sempre humana.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher

from scripts.audit.sources import SourceRecord
from scripts.reconcile_bncc_descriptions import _norm

LIMIAR_PADRAO = 0.92

STATUS_CONCORDANTE = "concordante"
STATUS_DIVERGENTE = "divergente"
STATUS_SEM_FONTES = "sem_fontes"


@dataclass(frozen=True)
class FonteComparacao:
    """Resultado da comparação do snapshot contra UMA fonte, para um código."""

    fonte: str
    presente: bool
    cobertura: float | None  # sinal de fidelidade; None se a fonte não conhece o código
    similaridade: float | None  # razão simétrica (informativa)
    descricao_fonte: str | None
    url: str | None


@dataclass
class ResultadoCodigo:
    """Veredito determinístico da auditoria de um código."""

    codigo: str
    etapa: str
    componente: str | None
    descricao_snapshot: str
    status: str
    limiar: float
    fontes: list[FonteComparacao] = field(default_factory=list)

    @property
    def melhor_cobertura(self) -> float | None:
        vals = [f.cobertura for f in self.fontes if f.cobertura is not None]
        return max(vals) if vals else None

    @property
    def fontes_divergentes(self) -> list[FonteComparacao]:
        return [
            f
            for f in self.fontes
            if f.presente and f.cobertura is not None and f.cobertura < self.limiar
        ]


def similaridade(a: str, b: str) -> float:
    """Razão de similaridade simétrica [0..1] entre dois textos, após normalização."""
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def cobertura(referencia: str, testemunha: str) -> float:
    """Fração de `referencia` (snapshot) sustentada por `testemunha`, após normalizar.

    Soma dos blocos casados dividida pelo tamanho da referência. Texto EXTRA na
    testemunha (bleed de coluna na extração) não penaliza — mede-se só quanto do
    texto oficial que servimos aparece na fonte.
    """
    ref = _norm(referencia)
    if not ref:
        return 0.0
    sm = SequenceMatcher(None, ref, _norm(testemunha))
    casado = sum(b.size for b in sm.get_matching_blocks())
    return casado / len(ref)


def comparar(
    hab: dict,
    registros: dict[str, SourceRecord | None],
    *,
    limiar: float = LIMIAR_PADRAO,
) -> ResultadoCodigo:
    """Compara uma habilidade do snapshot contra as testemunhas obtidas.

    `registros` mapeia slug-da-fonte -> SourceRecord (ou None se a fonte foi
    consultada mas não conhece o código). A ordem das fontes no resultado segue a
    ordem de inserção de `registros`.
    """
    codigo = str(hab.get("codigo", "?"))
    desc_snap = str(hab.get("descricao", ""))
    fontes: list[FonteComparacao] = []

    for slug, rec in registros.items():
        if rec is None:
            fontes.append(FonteComparacao(slug, False, None, None, None, None))
            continue
        cob = round(cobertura(desc_snap, rec.descricao), 4)
        sim = round(similaridade(desc_snap, rec.descricao), 4)
        fontes.append(FonteComparacao(slug, True, cob, sim, rec.descricao, rec.url))

    presentes = [f for f in fontes if f.presente]
    if not presentes:
        status = STATUS_SEM_FONTES
    elif all(f.cobertura is not None and f.cobertura < limiar for f in presentes):
        status = STATUS_DIVERGENTE
    else:
        status = STATUS_CONCORDANTE

    return ResultadoCodigo(
        codigo=codigo,
        etapa=str(hab.get("etapa", "?")),
        componente=hab.get("componente"),
        descricao_snapshot=desc_snap,
        status=status,
        limiar=limiar,
        fontes=fontes,
    )
