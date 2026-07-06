"""
Cobertura das rotas SSR do portal (T073 / Phase 8).

Exercita login/signup/verify-email/dashboard/keys/logout via TestClient,
incluindo o fluxo autenticado com cookie de sessão.
"""

import pytest
from app.services import account_service

VALID_PW = "senha-forte-123"  # pragma: allowlist secret


def test_login_page_renders(client):
    r = client.get("/portal/login")
    assert r.status_code == 200
    assert "form" in r.text.lower()


def test_signup_page_renders(client):
    r = client.get("/portal/signup")
    assert r.status_code == 200


def test_verify_email_missing_token(client):
    assert client.get("/portal/verify-email").status_code == 400


def test_verify_email_bad_token(client):
    assert client.get("/portal/verify-email?token=inexistente").status_code == 400


def test_login_bad_credentials(client):
    r = client.post(
        "/portal/login",
        data={"email": "ninguem@example.com", "password": "outra-senha-999"},
    )
    assert r.status_code == 401


def test_signup_then_duplicate(client):
    ok = client.post("/portal/signup", data={"email": "ssr@example.com", "password": VALID_PW})
    assert ok.status_code == 200  # renderiza login com aviso
    dup = client.post("/portal/signup", data={"email": "ssr@example.com", "password": VALID_PW})
    assert dup.status_code == 400


def test_dashboard_requires_session(client):
    r = client.get("/portal/dashboard", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"].endswith("/portal/login")


def test_keys_post_requires_session(client):
    r = client.post("/portal/keys", data={"name": "x"}, follow_redirects=False)
    assert r.status_code == 303


def test_logout_clears_cookie(client):
    r = client.get("/portal/logout", follow_redirects=False)
    assert r.status_code == 303


@pytest.mark.asyncio
async def test_verify_email_success_via_service(client, db_session):
    _account, token = await account_service.signup(db_session, "verify@example.com", VALID_PW)
    r = client.get(f"/portal/verify-email?token={token}")
    assert r.status_code == 200
    assert "verificado" in r.text.lower()


def test_full_authenticated_flow(client, onboarded_account):
    # login segue o redirect até o dashboard e fixa o cookie de sessão
    login = client.post("/portal/login", data={"email": "dev@example.com", "password": VALID_PW})
    assert login.status_code == 200

    dash = client.get("/portal/dashboard")
    assert dash.status_code == 200

    created = client.post("/portal/keys", data={"name": "minha-key"}, follow_redirects=False)
    assert created.status_code == 303
    # A key completa nunca vai na URL (histórico/logs/Referer) — trafega via
    # cookie httponly de uso único.
    assert created.headers["location"] == "/portal/dashboard"
    assert "flash_new_key" in created.cookies

    # dashboard agora lista a key recém-criada e exibe o segredo uma única vez
    dash2 = client.get("/portal/dashboard")
    assert dash2.status_code == 200
    assert "minha-key" in dash2.text
    assert "Sua nova API key" in dash2.text

    # segunda visita: o cookie de uso único já foi limpo, segredo não reaparece
    dash3 = client.get("/portal/dashboard")
    assert "Sua nova API key" not in dash3.text
