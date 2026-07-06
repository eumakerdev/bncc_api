"""
Teste de integração de SEO da landing page (US5 — T066).

Cobre: proposta de valor + CTA na home, metadados de SEO (meta description,
Open Graph, JSON-LD), `/sitemap.xml`, `/robots.txt` e HTML semântico com um
único <h1> (SC-008).
"""

from __future__ import annotations

import re


def test_landing_page_renders_value_prop_and_cta(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    body = response.text
    assert "BNCC" in body
    assert 'href="/portal/signup"' in body
    assert 'href="/guia"' in body


def test_landing_page_has_seo_metadata(client):
    body = client.get("/").text

    assert '<meta name="description"' in body
    assert 'property="og:title"' in body
    assert 'property="og:description"' in body
    assert 'property="og:type"' in body
    assert 'property="og:url"' in body
    assert 'property="og:image"' in body
    assert 'name="twitter:card"' in body
    assert "application/ld+json" in body
    assert '"@type": "WebSite"' in body


def test_landing_page_is_semantic_html_with_single_h1(client):
    body = client.get("/").text

    assert "<header" in body
    assert "<main" in body
    assert "<footer" in body
    assert body.count("<section") >= 1

    h1_matches = re.findall(r"<h1[ >]", body)
    assert len(h1_matches) == 1


def test_landing_page_has_use_cases_section(client):
    """A landing apresenta os 5 casos de uso reais como prova de valor (SC-008)."""
    body = client.get("/").text

    assert 'id="casos-de-uso"' in body
    # Os 5 casos pesquisados, ancorados em problemas reais:
    assert "plano" in body.lower()  # planos de aula com IA
    assert "recomposi" in body.lower()  # recomposição de aprendizagens
    assert "Computação" in body  # BNCC Computação 2026
    assert "cobertura" in body.lower()  # cobertura curricular
    assert "conteúdo" in body.lower()  # etiquetagem de conteúdo


def test_landing_page_shows_founders(client):
    """Evidencia Expertia e EuMaker como responsáveis pelo projeto."""
    body = client.get("/").text

    assert "expertia.dev.br" in body
    assert "eumaker.dev" in body
    assert "github.com/eumakerdev" in body


def test_landing_page_replicates_github_funding(client):
    """Replica os meios de apoio do GitHub: Sponsors + Pix (FUNDING.yml/README)."""
    body = client.get("/").text

    assert "github.com/sponsors/eumakerdev" in body
    assert "pix-qrcode.png" in body
    # Código Pix copia-e-cola presente (mesmo do README):
    assert "00020126580014br.gov.bcb.pix" in body


def test_landing_page_keeps_ai_marked_non_official(client):
    """Princípio IV/VII: conteúdo de IA sempre marcado como não-oficial."""
    body = client.get("/").text

    assert "não-oficial" in body


def test_site_url_overrides_canonical_and_sitemap(client, monkeypatch):
    """Com SITE_URL configurado, canonical/OG/sitemap usam o domínio primário e não
    a URL derivada do request (evita vazar a URL interna do Cloud Run atrás do proxy)."""
    from app.core import config

    monkeypatch.setattr(config.settings, "SITE_URL", "https://bncc.api.br")

    body = client.get("/").text
    assert 'rel="canonical" href="https://bncc.api.br/"' in body
    assert 'property="og:url" content="https://bncc.api.br/"' in body

    sitemap = client.get("/sitemap.xml").text
    assert "<loc>https://bncc.api.br/</loc>" in sitemap
    assert "run.app" not in sitemap

    robots = client.get("/robots.txt").text
    assert "Sitemap: https://bncc.api.br/sitemap.xml" in robots


def test_sitemap_xml(client):
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    assert "application/xml" in response.headers["content-type"]

    body = response.text
    assert "<urlset" in body
    assert "<loc>" in body
    assert "/guia" in body


def test_robots_txt(client):
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]

    body = response.text
    assert "User-agent:" in body
    assert "Sitemap:" in body
    assert "sitemap.xml" in body
