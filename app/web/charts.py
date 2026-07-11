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


def _fmt_month(d) -> str:
    """mm/aa — rótulo compacto do eixo X do gráfico de custos."""
    return f"{d.month:02d}/{d.year % 100:02d}"


def _fmt_brl_axis(n: float) -> str:
    """R$ inteiro com milhar por ponto (pt-BR) — rótulo do eixo Y de custos."""
    return "R$ " + f"{int(round(n)):,}".replace(",", ".")


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


# --------------------------------------------------------------------------- #
# Gráfico de área de série única — uso público diário (transparência)
# --------------------------------------------------------------------------- #
@dataclass
class UsagePoint:
    x: float
    y: float
    label: str  # dd/mm
    total: int


@dataclass
class PublicUsageChart:
    width: int = _WIDTH
    height: int = _HEIGHT
    baseline: float = _HEIGHT - _PAD_B
    max_value: int = 0
    has_data: bool = False
    line: str = ""
    area: str = ""
    points: list[UsagePoint] = field(default_factory=list)
    y_ticks: list[AxisTick] = field(default_factory=list)
    x_ticks: list[AxisTick] = field(default_factory=list)


def build_public_usage_chart(series: list) -> PublicUsageChart:
    """Monta a geometria do gráfico de área público (uma série: requisições/dia).

    Cada item de ``series`` expõe ``date`` e ``total``. Determinístico e testável:
    mesma escala "bonita" e mapeamento invertido do gráfico do painel, mas com uma
    única linha (sem separar sucesso/erro — Princípio da mínima exposição pública).
    """
    chart = PublicUsageChart()
    n = len(series)
    if n == 0:
        return chart

    peak = max((p.total for p in series), default=0)
    chart.has_data = peak > 0

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

    pts: list[str] = []
    for i, p in enumerate(series):
        x = round(x_at(i), 2)
        y = round(y_at(p.total), 2)
        pts.append(f"{x},{y}")
        chart.points.append(UsagePoint(x=x, y=y, label=_fmt_date(p.date), total=p.total))

    baseline = chart.baseline
    first_x = chart.points[0].x
    last_x = chart.points[-1].x
    chart.line = " ".join(pts)
    chart.area = f"M{first_x},{baseline} L" + " L".join(pts) + f" L{last_x},{baseline} Z"

    i = 0
    while i <= ticks:
        v = int(round(step * i))
        chart.y_ticks.append(AxisTick(pos=round(y_at(v), 2), label=_fmt_int(v)))
        i += 1

    max_labels = 7
    stride = max(1, math.ceil(n / max_labels))
    seen: set[int] = set()
    for idx in list(range(0, n, stride)) + [n - 1]:
        if idx in seen:
            continue
        seen.add(idx)
        chart.x_ticks.append(AxisTick(pos=round(x_at(idx), 2), label=chart.points[idx].label))
    return chart


# --------------------------------------------------------------------------- #
# Gráfico de barras empilhadas — custo mensal por serviço (transparência)
# --------------------------------------------------------------------------- #
@dataclass
class CostSegment:
    x: float
    y: float
    width: float
    height: float
    service: str  # slug do bucket (banco/servidor/ia/outros)
    color_class: str  # classe CSS do segmento
    label: str  # rótulo amigável
    amount: float
    title: str  # texto do <title> nativo (tooltip acessível sem JS)


@dataclass
class CostBar:
    label: str  # mm/aa
    total: float
    segments: list[CostSegment] = field(default_factory=list)


@dataclass
class CostLegendItem:
    service: str
    label: str
    color_class: str


@dataclass
class CostChart:
    width: int = _WIDTH
    height: int = _HEIGHT
    baseline: float = _HEIGHT - _PAD_B
    max_value: float = 0.0
    has_data: bool = False
    bars: list[CostBar] = field(default_factory=list)
    y_ticks: list[AxisTick] = field(default_factory=list)
    x_ticks: list[AxisTick] = field(default_factory=list)
    legend: list[CostLegendItem] = field(default_factory=list)


def _fmt_brl_full(n: float) -> str:
    """R$ com centavos (pt-BR) — usado no tooltip de cada segmento."""
    inteiro = f"{n:,.2f}"
    inteiro = inteiro.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {inteiro}"


def build_cost_chart(series: list) -> CostChart:
    """Monta a geometria do gráfico de barras empilhadas (custo mensal por serviço).

    Cada item de ``series`` expõe ``month`` (date), ``total`` (float) e
    ``by_service`` (lista com ``service`` [enum], ``label`` e ``amount``). Segmentos
    empilham na ordem canônica de ``by_service`` (base → topo). Puro/testável.
    """
    chart = CostChart()
    n = len(series)
    if n == 0:
        return chart

    peak = max((float(p.total) for p in series), default=0.0)
    chart.has_data = peak > 0
    if not chart.has_data:
        return chart

    ticks = 4
    nice_range = _nice_num(peak, round_up=True)
    step = _nice_num(nice_range / ticks, round_up=True)
    max_value = step * ticks
    chart.max_value = max_value

    plot_w = _WIDTH - _PAD_L - _PAD_R
    plot_h = _HEIGHT - _PAD_T - _PAD_B

    slot = plot_w / n
    bar_w = round(min(slot * 0.62, 56.0), 2)

    def y_at(v: float) -> float:
        return _PAD_T + plot_h * (1 - v / max_value)

    # Acumula presença de cada serviço para montar a legenda (só os com custo > 0).
    seen_service: dict[str, CostLegendItem] = {}

    for i, p in enumerate(series):
        center = _PAD_L + slot * (i + 0.5)
        x = round(center - bar_w / 2, 2)
        bar = CostBar(label=_fmt_month(p.month), total=round(float(p.total), 2))
        cum = 0.0
        for seg in p.by_service:
            amount = float(seg.amount)
            if amount <= 0:
                continue
            slug = seg.service.value if hasattr(seg.service, "value") else str(seg.service)
            color_class = f"cost-seg-{slug}"
            y_top = round(y_at(cum + amount), 2)
            y_bottom = round(y_at(cum), 2)
            title = f"{p.month.month:02d}/{p.month.year} · {seg.label}: {_fmt_brl_full(amount)}"
            bar.segments.append(
                CostSegment(
                    x=x,
                    y=y_top,
                    width=bar_w,
                    height=round(y_bottom - y_top, 2),
                    service=slug,
                    color_class=color_class,
                    label=seg.label,
                    amount=amount,
                    title=title,
                )
            )
            cum += amount
            if slug not in seen_service:
                seen_service[slug] = CostLegendItem(
                    service=slug, label=seg.label, color_class=color_class
                )
        chart.bars.append(bar)

    # Eixo Y "bonito".
    i = 0
    while i <= ticks:
        v = step * i
        chart.y_ticks.append(AxisTick(pos=round(y_at(v), 2), label=_fmt_brl_axis(v)))
        i += 1

    # Eixo X: rótulos de mês (todos até ~12; senão distribui, sempre o último).
    max_labels = 12
    stride = max(1, math.ceil(n / max_labels))
    seen: set[int] = set()
    for idx in list(range(0, n, stride)) + [n - 1]:
        if idx in seen:
            continue
        seen.add(idx)
        center = _PAD_L + slot * (idx + 0.5)
        chart.x_ticks.append(AxisTick(pos=round(center, 2), label=chart.bars[idx].label))

    chart.legend = list(seen_service.values())
    return chart
