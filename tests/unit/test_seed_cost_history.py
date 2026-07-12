"""
Testes das funções puras do semeador de histórico de custos
(scripts/seed_cost_history.py).

Cobre o parsing de números pt-BR, a inferência do mês pelo nome do arquivo e a
agregação do CSV do console (por serviço → bucket, custo líquido, rodapé ignorado).
Não toca o banco — usa o texto do CSV diretamente.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.db.tables import CostService
from scripts.seed_cost_history import aggregate_csv, month_from_filename, parse_brl

# Cabeçalho + linhas reais exportadas pelo console (Billing → Reports → Baixar CSV).
_CSV = (
    "Descrição do serviço,ID do serviço,Custo (R$),Programas de economia (R$),"
    "Outras economias (R$),Subtotal não arredondado (R$),Subtotal (R$),"
    "Mudança percentual no subtotal em comparação ao período anterior\n"
    'Cloud Run,152E-C115-5142,"91,14","0,00","- 30,73","60,416712","60,42",Novo\n'
    'Cloud SQL,9662-B51E-5089,"22,44","0,00","0,00","22,440751","22,44",Novo\n'
    'Cloud Build,8B5D-EF7D-EB12,"16,39","0,00","0,00","16,385511","16,39",Novo\n'
    'Artifact Registry,149C-F9EC-3994,"3,98","0,00","0,00","3,978499","3,98",Novo\n'
    'Gemini API,AEFD-7695-64FA,"0,55","0,00","0,00","0,545759","0,55",Novo\n'
    'Cloud Storage,95FF-2EF5-5EA1,"0,00","0,00","0,00","0,002970","0,00",Novo\n'
    ',,,,Subtotal,"103,770202","103,77"\n'
    ',,,,Tributo,"0,000000","0,00"\n'
    ',,,,Total filtrado,"103,770202","103,77"\n'
)


def test_parse_brl_formats():
    assert parse_brl("60,42") == Decimal("60.42")
    assert parse_brl("- 30,73") == Decimal("-30.73")
    assert parse_brl("1.234,56") == Decimal("1234.56")
    assert parse_brl("60,416712") == Decimal("60.416712")
    assert parse_brl("—") == Decimal("0")
    assert parse_brl("") == Decimal("0")


def test_month_from_filename():
    assert month_from_filename("🐞 [DEV]_Relatórios, 2026-07-01 — 2026-07-31.csv") == date(
        2026, 7, 1
    )
    assert month_from_filename("reports_2026-05.csv") == date(2026, 5, 1)
    assert month_from_filename("sem_data.csv") is None


def test_aggregate_csv_buckets_and_net():
    agg = aggregate_csv(_CSV)
    # Cloud Run → servidor (usa o subtotal não arredondado, líquido de economias).
    assert agg[CostService.servidor].quantize(Decimal("0.01")) == Decimal("60.42")
    # Cloud SQL → banco.
    assert agg[CostService.banco].quantize(Decimal("0.01")) == Decimal("22.44")
    # Gemini API → ia.
    assert agg[CostService.ia].quantize(Decimal("0.01")) == Decimal("0.55")
    # Cloud Build + Artifact Registry + Cloud Storage → outros (catch-all).
    assert agg[CostService.outros].quantize(Decimal("0.01")) == Decimal("20.37")


def test_aggregate_csv_ignores_footer_rows():
    # As linhas Subtotal/Tributo/Total filtrado (sem serviço) não viram buckets extras
    # nem inflam os totais — a soma dos buckets casa com o subtotal do relatório.
    agg = aggregate_csv(_CSV)
    total = sum(agg.values())
    assert total.quantize(Decimal("0.000001")) == Decimal("103.770202")
