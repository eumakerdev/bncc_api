"""
Schemas Pydantic da transparência pública de custos de infraestrutura.

Domínio distinto de contas/uso: alimenta a seção "Transparência de custos" da
landing (SSR), lida em runtime apenas do banco (``cost_records``). Valores em BRL,
por mês e por serviço, com totais e acumulado. Não é dado da BNCC (Princípio IV):
a origem é o faturamento real do GCP, claramente rotulada como custo de
infraestrutura — nunca confundida com o conteúdo oficial.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.db.tables import CostService

# Rótulos amigáveis (pt-BR) para cada bucket de serviço, na ordem de exibição.
SERVICE_LABELS: dict[CostService, str] = {
    CostService.banco: "Banco de dados",
    CostService.servidor: "Servidor",
    CostService.ia: "IA",
    CostService.outros: "Outros",
}
# Ordem canônica dos serviços (empilhamento do gráfico, legenda e breakdown).
SERVICE_ORDER: list[CostService] = [
    CostService.banco,
    CostService.servidor,
    CostService.ia,
    CostService.outros,
]


class CostServiceAmount(BaseModel):
    """Custo de um serviço num recorte (mês ou acumulado)."""

    service: CostService
    label: str = Field(..., description="Rótulo amigável do serviço (pt-BR)")
    amount: float = Field(..., description="Custo em BRL")


class CostMonthPoint(BaseModel):
    """Um ponto da série mensal: total do mês + breakdown por serviço."""

    month: date = Field(..., description="1º dia do mês (UTC)")
    total: float = Field(..., description="Custo total do mês em BRL")
    by_service: list[CostServiceAmount] = Field(
        ..., description="Custo por serviço no mês, na ordem canônica"
    )


class CostSummary(BaseModel):
    """Resumo público de custos: série mensal + KPIs agregados."""

    currency: str = "BRL"
    window_months: int
    has_data: bool = Field(False, description="Falso quando não há nenhum custo registrado")
    series: list[CostMonthPoint]
    period_start: date | None = Field(
        None, description="Mês mais antigo com custo registrado (rótulo 'desde ...')"
    )
    total_month: float = Field(0.0, description="Custo total do mês corrente em BRL")
    total_to_date: float = Field(
        0.0, description="Custo acumulado de TODOS os meses registrados (não só a janela)"
    )
    by_service_to_date: list[CostServiceAmount] = Field(
        default_factory=list, description="Custo acumulado por serviço (todos os meses)"
    )
