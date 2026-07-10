"""
Gráfico de área SSR determinístico (Princípio VII).

Converte a série diária de uso (``UsageDailyPoint``) em geometria SVG pronta para
o template — sem dependências de runtime, sem JS de renderização e sem CDN. O
mesmo dado alimenta a tabela acessível (fallback) no painel. Puro e testável:
recebe a série, devolve coordenadas/labels; não conhece HTTP nem o ORM.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# Sistema de coordenadas do viewBox (o SVG escala via CSS; unidades são internas).
_WIDTH = 840
_HEIGHT = 260
_PAD_L = 44
_PAD_R = 12
_PAD_T = 12
_PAD_B = 26


@dataclass
class ChartPoint:
    x: float
    y_total: float
    y_success: float
    label: str  # dd/mm
    total: int
    successful: int


@dataclass
class AxisTick:
    pos: float
    label: str


@dataclass
class UsageChart:
    width: int = _WIDTH
    height: int = _HEIGHT
    baseline: float = _HEIGHT - _PAD_B
    max_value: int = 0
    has_data: bool = False
    total_line: str = ""
    total_area: str = ""
    success_line: str = ""
    success_area: str = ""
    points: list[ChartPoint] = field(default_factory=list)
    y_ticks: list[AxisTick] = field(default_factory=list)
    x_ticks: list[AxisTick] = field(default_factory=list)


def _nice_num(value: float, round_up: bool) -> float:
    """Arredonda para um número "bonito" (1/2/5 × 10ⁿ) — eixos legíveis."""
    if value <= 0:
        return 1.0
    exp = math.floor(math.log10(value))
    frac = value / (10**exp)
    if round_up:
        nice = 1 if frac <= 1 else 2 if frac <= 2 else 5 if frac <= 5 else 10
    else:
        nice = 1 if frac < 1.5 else 2 if frac < 3 else 5 if frac < 7 else 10
    return nice * (10**exp)


def _fmt_int(n: int) -> str:
    """Milhar com ponto (pt-BR): 2500 → '2.500'."""
    return f"{n:,}".replace(",", ".")


def _fmt_date(d) -> str:
    return f"{d.day:02d}/{d.month:02d}"


def build_usage_chart(series: list) -> UsageChart:
    """Monta a geometria do gráfico de área (total vs. bem-sucedidas)."""
    chart = UsageChart()
    n = len(series)
    if n == 0:
        return chart

    peak = max((p.total for p in series), default=0)
    chart.has_data = peak > 0

    # Escala do eixo Y "bonita" com ~4 divisões (mínimo 4 p/ um eixo utilizável).
    ticks = 4
    nice_range = _nice_num(max(peak, 1), round_up=True)
    step = _nice_num(nice_range / ticks, round_up=True)
    max_value = int(step * ticks)
    if max_value < 4:
        max_value = 4
        step = max_value / ticks
    chart.max_value = max_value

    plot_w = _WIDTH - _PAD_L - _PAD_R
    plot_h = _HEIGHT - _PAD_T - _PAD_B

    def x_at(i: int) -> float:
        if n == 1:
            return _PAD_L + plot_w / 2
        return _PAD_L + plot_w * i / (n - 1)

    def y_at(v: int) -> float:
        return _PAD_T + plot_h * (1 - v / max_value)

    total_pts: list[str] = []
    success_pts: list[str] = []
    for i, p in enumerate(series):
        x = round(x_at(i), 2)
        yt = round(y_at(p.total), 2)
        ys = round(y_at(p.successful), 2)
        total_pts.append(f"{x},{yt}")
        success_pts.append(f"{x},{ys}")
        chart.points.append(
            ChartPoint(
                x=x,
                y_total=yt,
                y_success=ys,
                label=_fmt_date(p.date),
                total=p.total,
                successful=p.successful,
            )
        )

    baseline = chart.baseline
    first_x = chart.points[0].x
    last_x = chart.points[-1].x
    chart.total_line = " ".join(total_pts)
    chart.success_line = " ".join(success_pts)
    chart.total_area = (
        f"M{first_x},{baseline} L" + " L".join(total_pts) + f" L{last_x},{baseline} Z"
    )
    chart.success_area = (
        f"M{first_x},{baseline} L" + " L".join(success_pts) + f" L{last_x},{baseline} Z"
    )

    # Ticks do eixo Y.
    i = 0
    while i <= ticks:
        v = int(round(step * i))
        chart.y_ticks.append(AxisTick(pos=round(y_at(v), 2), label=_fmt_int(v)))
        i += 1

    # Ticks do eixo X: ~7 labels distribuídos, sempre incluindo o último dia.
    max_labels = 7
    stride = max(1, math.ceil(n / max_labels))
    seen: set[int] = set()
    for idx in list(range(0, n, stride)) + [n - 1]:
        if idx in seen:
            continue
        seen.add(idx)
        chart.x_ticks.append(AxisTick(pos=round(x_at(idx), 2), label=chart.points[idx].label))
    return chart
