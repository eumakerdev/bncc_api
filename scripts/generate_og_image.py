"""
Gera **todos** os assets raster da marca a partir de uma única paleta:

    app/web/static/og-image.png          1200x630  (og:image / twitter:image)
    app/web/static/favicon.ico           16/32/48
    app/web/static/apple-touch-icon.png  180x180   (iOS ignora SVG aqui)
    app/web/static/icon-192.png          192x192   (PWA / site.webmanifest)
    app/web/static/icon-512.png          512x512   (PWA / site.webmanifest)
    app/web/static/logo-300.png          300x300
    app/web/static/linkedin-banner.png   1584x396
    app/web/static/linkedin-cover.png    1128x191

Redes sociais (Facebook/WhatsApp/Twitter/LinkedIn) não aceitam SVG como
`og:image`; navegadores e crawlers pedem `/favicon.ico` na raiz. Este script
desenha tudo programaticamente a partir da identidade visual do site
("leitor em camadas": tile verde-mata -> verde-bandeira, três chevrons brancos
e ponto de ouro — o mesmo desenho de `logo-icon.svg` e do macro
`templates/_brand.html`), de forma determinística e reproduzível: os assets
commitados são sempre regeneráveis daqui.

Determinismo: a tipografia vem da Inter versionada em `app/web/static/fonts/`.
Antes o script caçava fontes do sistema, e o mesmo comando produzia arquivos
diferentes no Windows e no CI. Se a fonte versionada não puder ser usada, ele
cai no stack do sistema **e avisa** — o desvio não pode ser silencioso.

Pillow e fonttools são dependências **somente desta ferramenta** (não entram no
requirements.txt para não inchar a imagem de produção):

    venv/Scripts/pip install pillow fonttools brotli
    venv/Scripts/python scripts/generate_og_image.py
"""

from __future__ import annotations

from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parent.parent / "app" / "web" / "static"
FONT_DIR = STATIC_DIR / "fonts"

# Paleta da marca — leitura sóbria da bandeira. Espelha os tokens de
# styles.css (--mark-a/--mark-b/--mark-dot, --ground, --brand). Ver DESIGN.md.
GROUND = (11, 18, 14)  # #0b120e  verde-noite
MARK_A = (7, 96, 58)  # #07603a  verde-mata
MARK_B = (18, 164, 90)  # #12a45a  verde-bandeira
GOLD = (242, 192, 74)  # #f2c04a  ouro (o "estudante")
WHITE = (255, 255, 255)
MUTED = (164, 171, 182)  # #a4abb6  --ink-muted do tema escuro
BRAND_LIGHT = (95, 188, 118)  # #5fbc76  --brand do tema escuro

TITLE = "BNCC API"
SUBTITLE = [
    "Toda a Base Nacional Comum Curricular",
    "do Brasil em uma API gratuita",
]
SITE = "bncc.api.br"

# Fonte versionada da marca (Inter variable, subset latin). O eixo de peso é
# instanciado em memória: o Pillow não seleciona eixos variáveis por conta.
_INTER_VARIABLE = FONT_DIR / "inter-latin.woff2"

# Fallback do sistema, só se a fonte versionada não estiver disponível.
_FONT_FALLBACKS = [
    "C:/Windows/Fonts/seguisb.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

_font_source_reported = False
_inter_cache: dict[float, bytes | None] = {}


def _inter_ttf_bytes(weight: float) -> bytes | None:
    """Converte o woff2 variável da Inter em um TTF estático no peso pedido."""
    try:
        from io import BytesIO

        from fontTools.ttLib import TTFont
        from fontTools.varLib.instancer import instantiateVariableFont
    except ImportError:
        return None
    if not _INTER_VARIABLE.exists():
        return None
    font = TTFont(str(_INTER_VARIABLE))  # fontTools lê woff2 quando há brotli
    instantiateVariableFont(font, {"wght": weight}, inplace=True, updateFontNames=False)
    buf = BytesIO()
    font.save(buf)
    return buf.getvalue()


def _font(size: int, weight: float = 700):
    """Fonte da marca no tamanho pedido — versionada, com aviso se cair no fallback."""
    global _font_source_reported
    from io import BytesIO

    from PIL import ImageFont

    if weight not in _inter_cache:
        _inter_cache[weight] = _inter_ttf_bytes(weight)
    data = _inter_cache[weight]
    if data is not None:
        if not _font_source_reported:
            print(f"    fonte: Inter versionada ({_INTER_VARIABLE.name}) — determinístico")
            _font_source_reported = True
        return ImageFont.truetype(BytesIO(data), size)

    for path in _FONT_FALLBACKS:
        if Path(path).exists():
            if not _font_source_reported:
                print(f"    AVISO fonte do sistema ({path}) — saída NAO deterministica.")
                print("          instale `fonttools brotli` para usar a Inter versionada.")
                _font_source_reported = True
            return ImageFont.truetype(path, size)
    if not _font_source_reported:
        print("    AVISO fonte default do Pillow — saída NAO deterministica.")
        _font_source_reported = True
    return ImageFont.load_default(size)


def _diagonal_gradient(width: int, height: int, color_a, color_b):
    """Gradiente diagonal (topo-esquerda → base-direita) entre duas cores."""
    from PIL import Image

    ramp = Image.linear_gradient("L").rotate(45, expand=True).resize((width, height))
    solid_a = Image.new("RGB", (width, height), color_a)
    solid_b = Image.new("RGB", (width, height), color_b)
    return Image.composite(solid_b, solid_a, ramp)


def _draw_brand_tile(size: int):
    """Tile da marca (equivalente ao macro de _brand.html), em `size` px."""
    from PIL import Image, ImageDraw

    scale = 8  # desenha grande e reduz para suavizar bordas (anti-alias)
    big = size * scale
    unit = big / 48  # o SVG original usa viewBox 0 0 48 48

    tile = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    gradient = _diagonal_gradient(big, big, MARK_A, MARK_B).convert("RGBA")
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [4 * unit, 4 * unit, 44 * unit, 44 * unit], radius=12 * unit, fill=255
    )
    tile.paste(gradient, (0, 0), mask)

    draw = ImageDraw.Draw(tile)
    # Três chevrons "livro aberto" (stroke branco 3.5, caps/joins redondos).
    stroke = 3.5 * unit
    for y0 in (22, 28.6, 35.2):
        points = [(13 * unit, y0 * unit), (24 * unit, (y0 + 4.5) * unit), (35 * unit, y0 * unit)]
        draw.line(points, fill=WHITE, width=round(stroke), joint="curve")
        for px, py in (points[0], points[-1]):  # caps redondos nas pontas
            cap = stroke / 2
            draw.ellipse([px - cap, py - cap, px + cap, py + cap], fill=WHITE)
    # O "estudante": ponto de ouro sobre o livro.
    draw.ellipse(
        [(24 - 3.3) * unit, (13.8 - 3.3) * unit, (24 + 3.3) * unit, (13.8 + 3.3) * unit],
        fill=GOLD,
    )
    return tile.resize((size, size), Image.LANCZOS)


def _dark_ground(width: int, height: int, glow_box):
    """Fundo verde-noite com o brilho da marca — base comum dos cards sociais.

    O brilho é uma elipse BORRADA, não uma elipse translúcida: sem o blur ela
    tem borda dura e lê como um disco colado no fundo, não como luz.
    """
    from PIL import Image, ImageDraw, ImageFilter

    img = Image.new("RGB", (width, height), GROUND)
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).ellipse(glow_box, fill=70)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=max(width, height) * 0.12))
    glow = Image.new("RGB", (width, height), MARK_B)
    return Image.composite(glow, img, mask)


def build_og_image():
    """Card social 1200×630: fundo verde-noite, tile da marca, título e subtítulo."""
    from PIL import ImageDraw

    width, height = 1200, 630
    img = _dark_ground(width, height, [760, -320, 1560, 480])
    draw = ImageDraw.Draw(img)

    # Barra de acento na base (gradiente da marca).
    img.paste(_diagonal_gradient(width, 10, MARK_A, MARK_B), (0, height - 10))

    tile = _draw_brand_tile(128)
    img.paste(tile, (96, 96), tile)

    draw.text((96, 268), TITLE, font=_font(104), fill=WHITE)
    subtitle_font = _font(44, weight=500)
    for i, line in enumerate(SUBTITLE):
        draw.text((96, 408 + i * 60), line, font=subtitle_font, fill=MUTED)
    draw.text((96, 546), SITE, font=_font(34, weight=600), fill=BRAND_LIGHT)

    return img


def build_linkedin_banner(width: int, height: int):
    """Banner/cover do LinkedIn: mesma marca, em proporção panorâmica."""
    from PIL import ImageDraw

    glow = [width - 480, -int(height * 0.9), width + 320, int(height * 1.1)]
    img = _dark_ground(width, height, glow)
    draw = ImageDraw.Draw(img)

    accent = max(4, round(height / 46))
    img.paste(_diagonal_gradient(width, accent, MARK_A, MARK_B), (0, height - accent))

    tile_size = round(height * 0.42)
    pad = round(height * 0.20)
    tile = _draw_brand_tile(tile_size)
    img.paste(tile, (pad, (height - tile_size) // 2), tile)

    text_x = pad + tile_size + round(height * 0.13)
    title_size = round(height * 0.20)
    sub_size = round(height * 0.098)

    # Três linhas com respiro entre elas, centradas em bloco no eixo vertical —
    # centrar cada linha por conta deixava o conjunto colado e fora de eixo.
    lines = [
        (TITLE, _font(title_size), WHITE, title_size * 1.10),
        (
            "Toda a Base Nacional Comum Curricular, via API",
            _font(sub_size, weight=500),
            MUTED,
            sub_size * 1.55,
        ),
        (SITE, _font(sub_size, weight=600), BRAND_LIGHT, sub_size * 1.20),
    ]
    block = sum(advance for *_, advance in lines)
    y = height / 2 - block / 2
    for text, font, fill, advance in lines:
        draw.text((text_x, y), text, font=font, fill=fill)
        y += advance
    return img


def main() -> None:
    outputs: list[tuple[str, str]] = []

    og_path = STATIC_DIR / "og-image.png"
    build_og_image().save(og_path, format="PNG", optimize=True)
    outputs.append((og_path.name, "1200x630"))

    # O favicon .ico e os ícones do manifest saem todos do mesmo tile.
    ico_path = STATIC_DIR / "favicon.ico"
    _draw_brand_tile(48).save(ico_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])
    outputs.append((ico_path.name, "16/32/48"))

    for name, size in (
        ("apple-touch-icon.png", 180),
        ("icon-192.png", 192),
        ("icon-512.png", 512),
        ("logo-300.png", 300),
    ):
        path = STATIC_DIR / name
        _draw_brand_tile(size).save(path, format="PNG", optimize=True)
        outputs.append((name, f"{size}x{size}"))

    for name, (width, height) in (
        ("linkedin-banner.png", (1584, 396)),
        ("linkedin-cover.png", (1128, 191)),
    ):
        path = STATIC_DIR / name
        build_linkedin_banner(width, height).save(path, format="PNG", optimize=True)
        outputs.append((name, f"{width}x{height}"))

    for name, dims in outputs:
        print(f"OK  {STATIC_DIR / name} ({dims})")


if __name__ == "__main__":
    main()
