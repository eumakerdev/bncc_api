"""
Testes unitários do gerador de gráfico SSR (app/web/charts.py).

Geometria determinística: escala "bonita" do eixo, mapeamento invertido (valor
maior → mais alto na tela), rótulos de eixo e estados de borda (vazio/1 ponto).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from app.db.tables import CostService
from app.models.cost import SERVICE_LABELS, SERVICE_ORDER, CostMonthPoint, CostServiceAmount
from app.models.platform import PublicUsagePoint, UsageDailyPoint
from app.web.charts import build_cost_chart, build_public_usage_chart, build_usage_chart


def _series(values: list[tuple[int, int]], start: date | None = None) -> list[UsageDailyPoint]:
    start = start or date(2026, 7, 1)
    return [
        UsageDailyPoint(date=start + timedelta(days=i), total=t, successful=s, failed=t - s)
        for i, (t, s) in enumerate(values)
    ]


def test_empty_series_has_no_data():
    chart = build_usage_chart([])
    assert chart.has_data is False
    assert chart.points == []
    assert chart.total_line == ""


def test_all_zero_series_is_flagged_empty_but_valid_axes():
    chart = build_usage_chart(_series([(0, 0)] * 5))
    assert chart.has_data is False
    assert len(chart.points) == 5
    assert chart.max_value >= 4  # eixo utilizável mesmo sem tráfego
    assert chart.y_ticks  # rótulos do eixo Y existem


def test_nice_max_covers_peak():
    chart = build_usage_chart(_series([(0, 0), (772, 700), (1250, 1180)]))
    assert chart.has_data is True
    assert chart.max_value >= 1250
    # Escala com 4 divisões → 5 rótulos (0 … max), topo "bonito" acima do pico.
    assert len(chart.y_ticks) == 5
    assert chart.y_ticks[0].label == "0"


def test_higher_value_maps_higher_on_screen():
    chart = build_usage_chart(_series([(100, 100), (1000, 900)]))
    p_low, p_high = chart.points
    # y cresce para baixo no SVG: total maior deve ter y MENOR (mais no topo).
    assert p_high.y_total < p_low.y_total
    # Bem-sucedidas <= total → linha de sucesso nunca acima da de total.
    assert p_high.y_success >= p_high.y_total


def test_paths_and_labels_shape():
    series = _series([(10, 9), (20, 18), (30, 30)])
    chart = build_usage_chart(series)
    assert chart.total_area.startswith("M")
    assert chart.total_area.endswith("Z")
    assert len(chart.total_line.split(" ")) == 3
    # O último dia sempre rotulado no eixo X.
    assert chart.x_ticks[-1].label == "03/07"
    assert chart.points[0].label == "01/07"


def test_single_point_is_centered():
    chart = build_usage_chart(_series([(50, 40)]))
    assert len(chart.points) == 1
    # Ponto único fica no centro horizontal da área de plotagem (entre as margens).
    assert 400 < chart.points[0].x < 470


# --------------------------------------------------------------------------- #
# Gráfico de uso público (área de série única — requisições/dia)
# --------------------------------------------------------------------------- #
def _usage_series(totals: list[int], start: date | None = None) -> list[PublicUsagePoint]:
    start = start or date(2026, 7, 1)
    return [PublicUsagePoint(date=start + timedelta(days=i), total=t) for i, t in enumerate(totals)]


def test_public_usage_empty_has_no_data():
    chart = build_public_usage_chart([])
    assert chart.has_data is False
    assert chart.points == []
    assert chart.line == ""
    assert chart.area == ""


def test_public_usage_all_zero_is_empty_but_valid_axes():
    chart = build_public_usage_chart(_usage_series([0] * 7))
    assert chart.has_data is False
    assert len(chart.points) == 7
    assert chart.max_value >= 4  # eixo utilizável mesmo sem tráfego
    assert chart.y_ticks


def test_public_usage_nice_max_and_paths():
    chart = build_public_usage_chart(_usage_series([120, 890, 1250]))
    assert chart.has_data is True
    assert chart.max_value >= 1250
    assert len(chart.y_ticks) == 5
    assert chart.area.startswith("M")
    assert chart.area.endswith("Z")
    assert len(chart.line.split(" ")) == 3
    # O último dia sempre rotulado no eixo X.
    assert chart.x_ticks[-1].label == "03/07"


def test_public_usage_higher_value_maps_higher():
    chart = build_public_usage_chart(_usage_series([100, 1000]))
    p_low, p_high = chart.points
    # y cresce para baixo no SVG: total maior deve ter y MENOR (mais no topo).
    assert p_high.y < p_low.y


def test_public_usage_single_point_centered():
    chart = build_public_usage_chart(_usage_series([50]))
    assert len(chart.points) == 1
    assert 400 < chart.points[0].x < 470


# --------------------------------------------------------------------------- #
# Gráfico de custo (barras empilhadas por serviço)
# --------------------------------------------------------------------------- #
def _cost_month(month: date, amounts: dict[CostService, float]) -> CostMonthPoint:
    by_service = [
        CostServiceAmount(service=s, label=SERVICE_LABELS[s], amount=amounts.get(s, 0.0))
        for s in SERVICE_ORDER
    ]
    total = round(sum(item.amount for item in by_service), 2)
    return CostMonthPoint(month=month, total=total, by_service=by_service)


def test_cost_empty_series_has_no_data():
    chart = build_cost_chart([])
    assert chart.has_data is False
    assert chart.bars == []
    assert chart.legend == []


def test_cost_all_zero_series_is_empty():
    series = [_cost_month(date(2026, 1, 1), {}), _cost_month(date(2026, 2, 1), {})]
    chart = build_cost_chart(series)
    assert chart.has_data is False


def test_cost_stacking_and_axes():
    series = [
        _cost_month(
            date(2026, 5, 1),
            {CostService.banco: 50, CostService.servidor: 90, CostService.ia: 20},
        ),
        _cost_month(date(2026, 6, 1), {CostService.banco: 52, CostService.servidor: 90}),
    ]
    chart = build_cost_chart(series)
    assert chart.has_data is True
    assert chart.max_value >= 160  # topo "bonito" acima do pico (50+90+20)
    assert len(chart.y_ticks) == 5
    # Legenda na ordem canônica de aparição (outros não aparece: custo 0).
    assert [item.service for item in chart.legend] == ["banco", "servidor", "ia"]

    first = chart.bars[0]
    assert len(first.segments) == 3
    # A base do empilhamento toca a linha de base do gráfico.
    bottoms = [seg.y + seg.height for seg in first.segments]
    assert max(bottoms) == pytest.approx(chart.baseline, abs=0.5)
    # Soma das alturas dos segmentos = do baseline ao topo (total do mês).
    top = min(seg.y for seg in first.segments)
    assert sum(seg.height for seg in first.segments) == pytest.approx(chart.baseline - top, abs=0.6)


def test_cost_single_month_one_service():
    chart = build_cost_chart([_cost_month(date(2026, 7, 1), {CostService.servidor: 120})])
    assert chart.has_data is True
    assert len(chart.bars) == 1
    assert len(chart.bars[0].segments) == 1
    assert chart.bars[0].segments[0].service == "servidor"
    assert chart.x_ticks[-1].label == "07/26"
