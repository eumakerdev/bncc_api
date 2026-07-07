"""
Gera os assets estáticos de SEO: `app/web/static/og-image.png` (1200×630) e
`app/web/static/favicon.ico` (16/32/48px).

Redes sociais (Facebook/WhatsApp/Twitter/LinkedIn) não aceitam SVG como
`og:image`; navegadores e crawlers pedem `/favicon.ico` na raiz. Este script
desenha ambos programaticamente a partir da identidade visual do site
("leitor em camadas": tile #1b4dff→#0aa8dc, três chevrons brancos e ponto
amarelo — o mesmo desenho de `logo-icon.svg`/`base.html`), de forma
determinística e reproduzível: os assets commitados são sempre regeneráveis daqui.

Pillow é dependência **somente desta ferramenta** (não entra no
requirements.txt para não inchar a imagem de produção):

    venv/Scripts/pip install pillow
    venv/Scripts/python scripts/generate_og_image.py
"""

from __future__ import annotations

from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parent.parent / "app" / "web" / "static"

# Paleta do site (ver logo-icon.svg / base.html / styles.css).
BG_DARK = (13, 15, 20)  # #0d0f14
BRAND_A = (27, 77, 255)  # #1b4dff
BRAND_B = (10, 168, 220)  # #0aa8dc
YELLOW = (255, 197, 61)  # #ffc53d
WHITE = (255, 255, 255)
MUTED = (176, 184, 201)

TITLE = "BNCC API"
SUBTITLE = [
    "Toda a Base Nacional Comum Curricular",
    "do Brasil em uma API gratuita",
]
SITE = "bncc.api.br"

# Fontes bold do sistema, em ordem de preferência (Windows → Linux/CI).
_FONT_CANDIDATES = [
    "C:/Windows/Fonts/seguisb.ttf",  # Segoe UI Semibold
    "C:/Windows/Fonts/segoeuib.ttf",  # Segoe UI Bold
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _font(size: int):
    from PIL import ImageFont

    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def _diagonal_gradient(width: int, height: int, color_a, color_b):
    """Gradiente diagonal (topo-esquerda → base-direita) entre duas cores."""
    from PIL import Image

    ramp = Image.linear_gradient("L").rotate(45, expand=True).resize((width, height))
    solid_a = Image.new("RGB", (width, height), color_a)
    solid_b = Image.new("RGB", (width, height), color_b)
    return Image.composite(solid_b, solid_a, ramp)


def _draw_brand_tile(size: int):
    """Tile da marca (equivalente ao SVG inline de base.html), em `size` px."""
    from PIL import Image, ImageDraw

    scale = 8  # desenha grande e reduz para suavizar bordas (anti-alias)
    big = size * scale
    unit = big / 48  # o SVG original usa viewBox 0 0 48 48

    tile = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    gradient = _diagonal_gradient(big, big, BRAND_A, BRAND_B).convert("RGBA")
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
    # O "estudante": ponto amarelo sobre o livro.
    draw.ellipse(
        [(24 - 3.3) * unit, (13.8 - 3.3) * unit, (24 + 3.3) * unit, (13.8 + 3.3) * unit],
        fill=YELLOW,
    )
    return tile.resize((size, size), Image.LANCZOS)


def build_og_image():
    """Card social 1200×630: fundo escuro, tile da marca, título e subtítulo."""
    from PIL import Image, ImageDraw

    width, height = 1200, 630
    img = Image.new("RGB", (width, height), BG_DARK)
    draw = ImageDraw.Draw(img)

    # Brilho sutil da marca no canto superior direito (grande círculo translúcido).
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([760, -320, 1560, 480], fill=(*BRAND_A, 46))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Barra de acento na base (gradiente da marca).
    img.paste(_diagonal_gradient(width, 10, BRAND_A, BRAND_B), (0, height - 10))

    tile = _draw_brand_tile(128)
    img.paste(tile, (96, 96), tile)

    draw.text((96, 268), TITLE, font=_font(104), fill=WHITE)
    subtitle_font = _font(44)
    for i, line in enumerate(SUBTITLE):
        draw.text((96, 408 + i * 60), line, font=subtitle_font, fill=MUTED)
    draw.text((96, 546), SITE, font=_font(34), fill=BRAND_B)

    return img


def main() -> None:
    og_path = STATIC_DIR / "og-image.png"
    build_og_image().save(og_path, format="PNG", optimize=True)
    print(f"OK  {og_path} (1200x630)")

    ico_path = STATIC_DIR / "favicon.ico"
    base = _draw_brand_tile(48)
    base.save(ico_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])
    print(f"OK  {ico_path} (16/32/48)")


if __name__ == "__main__":
    main()
