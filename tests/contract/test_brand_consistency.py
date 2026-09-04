"""
Portão de consistência da marca.

Motivação (auditoria 2026-09-04): o símbolo da BNCC API tinha virado onze
cópias divergentes — sete SVGs colados à mão nos templates e quatro arquivos em
`static/` — em quatro paletas paralelas. O admin chegou a renderizar um mark
com **dois** chevrons e sem o ponto do estudante, e ninguém percebeu: nada
quebra quando a marca se fragmenta, ela só para de ser uma marca.

Por isso o portão é versionado, no mesmo espírito de
`tests/integration/test_lazy_ai_startup.py`: a regressão aqui é invisível para
qualquer outro teste. As regras duras vivem em `DESIGN.md`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
APP = REPO / "app"
SCRIPTS = REPO / "scripts"
STATIC = APP / "web" / "static"
TEMPLATES = APP / "web" / "templates"

# Paleta anterior (azul elétrico → ciano + âmbar), incluindo as variantes de
# tema escuro e o #0d0f14 que nunca foi token. Nenhuma pode voltar.
PALETA_ANTIGA = ["1b4dff", "0aa8dc", "ffc53d", "5b7bff", "2f5bff", "1fc0f2", "0d0f14"]

# A logo do Google é marca de terceiro: as quatro cores oficiais são fiéis por
# obrigação, não divergência nossa.
HEX_DE_TERCEIROS = {"4285f4", "34a853", "fbbc05", "ea4335"}

# O desenho canônico do símbolo: três chevrons (as três etapas da BNCC) e o
# ponto do estudante acima deles.
CHEVRONS = [
    "M13 22l11 4.5L35 22",
    "M13 28.6l11 4.5 11-4.5",
    "M13 35.2l11 4.5 11-4.5",
]
PONTO_ESTUDANTE = re.compile(r'cx="24"\s+cy="13.8"\s+r="3.3"')

SVGS_DA_MARCA = ["logo.svg", "logo-dark.svg", "logo-icon.svg"]


def _fontes_do_app() -> list[Path]:
    arquivos: list[Path] = []
    for raiz in (APP, SCRIPTS):
        for ext in ("*.html", "*.css", "*.py", "*.svg", "*.webmanifest"):
            arquivos.extend(raiz.rglob(ext))
    return [p for p in arquivos if "__pycache__" not in p.parts]


@pytest.mark.parametrize("hexa", PALETA_ANTIGA)
def test_paleta_antiga_nao_ressuscita(hexa: str) -> None:
    """Nenhum hex da identidade azul sobrevive em app/ ou scripts/."""
    culpados = []
    for arquivo in _fontes_do_app():
        texto = arquivo.read_text(encoding="utf-8", errors="ignore")
        for numero, linha in enumerate(texto.splitlines(), 1):
            if hexa in linha.lower():
                # Comentários podem citar o valor antigo para explicar a troca.
                if "Antes era" in linha or "antes era" in linha:
                    continue
                culpados.append(f"{arquivo.relative_to(REPO)}:{numero}")
    assert not culpados, f"cor da identidade antiga (#{hexa}) reapareceu em: {culpados}"


def test_simbolo_so_existe_no_macro() -> None:
    """Nenhum template redesenha o símbolo: todos importam `_brand.html`."""
    reincidentes = []
    for template in TEMPLATES.rglob("*.html"):
        if template.name == "_brand.html":
            continue
        if "linearGradient" in template.read_text(encoding="utf-8"):
            reincidentes.append(str(template.relative_to(REPO)))
    assert not reincidentes, (
        "template desenhando o símbolo por conta própria (use "
        f'{{% from "_brand.html" import mark %}}): {reincidentes}'
    )


def test_macro_parametriza_o_id_do_gradiente() -> None:
    """base.html e portal/login.html coexistem numa página: ids não podem colidir."""
    macro = (TEMPLATES / "_brand.html").read_text(encoding="utf-8")
    assert 'id="bncc-tile-{{ uid }}"' in macro, "o id do gradiente precisa depender de `uid`"


@pytest.mark.parametrize("nome", SVGS_DA_MARCA)
def test_svgs_da_marca_desenham_o_mesmo_simbolo(nome: str) -> None:
    """As três etapas e o ponto do estudante estão em TODA variante do logo."""
    svg = (STATIC / nome).read_text(encoding="utf-8")
    for chevron in CHEVRONS:
        assert chevron in svg, f"{nome} não tem o chevron `{chevron}` (as 3 etapas da BNCC)"
    assert PONTO_ESTUDANTE.search(svg), f"{nome} perdeu o ponto do estudante"


def test_macro_desenha_o_mesmo_simbolo_dos_svgs() -> None:
    """O desenho inline não pode divergir dos arquivos .svg."""
    macro = (TEMPLATES / "_brand.html").read_text(encoding="utf-8")
    for chevron in CHEVRONS:
        assert chevron in macro, f"o macro perdeu o chevron `{chevron}`"
    assert PONTO_ESTUDANTE.search(macro), "o macro perdeu o ponto do estudante"


def test_simbolo_nunca_e_recolorido_fora_dos_tokens() -> None:
    """O macro tira a cor de --mark-*; recolorir o mark foi o que gerou divergência."""
    macro = (TEMPLATES / "_brand.html").read_text(encoding="utf-8")
    assert 'class="mark-a"' in macro and 'class="mark-b"' in macro
    assert 'class="mark-dot"' in macro
    css = (STATIC / "styles.css").read_text(encoding="utf-8")
    for token in ("--mark-a", "--mark-b", "--mark-dot"):
        # Definido nos dois temas (claro + bloco prefers-color-scheme: dark).
        assert css.count(f"  {token}:") >= 1, f"{token} não é definido no tema claro"
        assert css.count(f"    {token}:") >= 1, f"{token} não é definido no tema escuro"


def test_theme_color_igual_em_todas_as_superficies() -> None:
    """A barra do navegador é a mesma na landing e na referência da API."""
    padrao = re.compile(r'name="theme-color" content="(#[0-9a-fA-F]{6})"')
    valores = {}
    for nome in ("base.html", "reference.html"):
        valores[nome] = padrao.findall((TEMPLATES / nome).read_text(encoding="utf-8"))
    assert valores["base.html"], "base.html perdeu o theme-color"
    assert (
        valores["base.html"] == valores["reference.html"]
    ), f"theme-color divergente entre superfícies: {valores}"


def test_hex_literal_nao_volta_para_os_templates() -> None:
    """Cor em template é divergência esperando acontecer: use os tokens."""
    padrao = re.compile(r"#([0-9a-fA-F]{6})\b")
    vazamentos = []
    for template in TEMPLATES.rglob("*.html"):
        for numero, linha in enumerate(template.read_text(encoding="utf-8").splitlines(), 1):
            for hexa in padrao.findall(linha):
                if hexa.lower() in HEX_DE_TERCEIROS:
                    continue
                if "theme-color" in linha:  # meta tag não aceita var()
                    continue
                if template.name == "reference.html":  # Scalar não carrega o design system
                    continue
                if template.name == "_brand.html" and hexa.lower() == "ffffff":
                    # Os chevrons são brancos nos DOIS temas: eles vivem sobre o
                    # tile, que é sempre verde. Tokenizá-los seria convidar
                    # alguém a repintar o símbolo — exatamente o defeito que os
                    # carrosséis do LinkedIn tinham.
                    continue
                vazamentos.append(f"{template.relative_to(REPO)}:{numero} -> #{hexa}")
    assert not vazamentos, f"cor literal em template (use var(--token)): {vazamentos}"


def test_assets_raster_da_marca_existem() -> None:
    """Tudo que `generate_og_image.py` promete gerar está commitado."""
    esperados = [
        "og-image.png",
        "favicon.ico",
        "apple-touch-icon.png",
        "icon-192.png",
        "icon-512.png",
        "logo-300.png",
        "linkedin-banner.png",
        "linkedin-cover.png",
        "site.webmanifest",
        "fonts/inter-latin.woff2",
    ]
    faltando = [nome for nome in esperados if not (STATIC / nome).exists()]
    assert not faltando, f"asset da marca ausente (rode scripts/generate_og_image.py): {faltando}"


def test_og_image_svg_continua_morto() -> None:
    """A cópia stale do card social contradizia o PNG servido — não pode voltar."""
    assert not (
        STATIC / "og-image.svg"
    ).exists(), "og-image.svg foi recriado; o card social vem de scripts/generate_og_image.py"


def test_fonte_da_marca_e_carregada_onde_e_declarada() -> None:
    """Inter foi declarada por meses sem nunca ser baixada — o site caía no sistema."""
    assert (STATIC / "fonts.css").exists()
    for nome in ("base.html", "reference.html", "admin/base.html", "admin/login.html"):
        html = (TEMPLATES / nome).read_text(encoding="utf-8")
        assert "/static/fonts.css" in html, f"{nome} usa Inter sem carregá-la"
