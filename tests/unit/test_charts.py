"""
Testes unitários do gerador de gráfico SSR (app/web/charts.py).

Geometria determinística: escala "bonita" do eixo, mapeamento invertido (valor
maior → mais alto na tela), rótulos de eixo e estados de borda (vazio/1 ponto).
"""

from __future__ import annotations

from datetime import date, timedelta

from app.models.platform import UsageDailyPoint
from app.web.charts import build_usage_chart


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
