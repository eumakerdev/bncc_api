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
