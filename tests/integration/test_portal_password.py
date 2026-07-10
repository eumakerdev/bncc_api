"""
Cobertura SSR do painel redesenhado (BI) e dos fluxos de senha no portal.

Exercita as páginas públicas (esqueci/redefinir), a troca de senha autenticada e
a renderização do dashboard com a seção de analytics.
"""

VALID_PW = "senha-forte-123"  # pragma: allowlist secret


# --------------------------------------------------------------------------- #
# Páginas públicas de recuperação
# --------------------------------------------------------------------------- #
def test_forgot_password_page_renders(client):
    r = client.get("/portal/forgot-password")
    assert r.status_code == 200
    assert "Recuperar senha" in r.text


def test_forgot_password_submit_is_neutral(client):
    r = client.post("/portal/forgot-password", data={"email": "ninguem@example.com"})
    assert r.status_code == 200
    assert "link de redefinição" in r.text.lower()


def test_reset_password_page_requires_token(client):
    r = client.get("/portal/reset-password")
    assert r.status_code == 400


def test_reset_password_page_with_token_renders(client):
    r = client.get("/portal/reset-password?token=abc123def456")
    assert r.status_code == 200
    assert "Criar nova senha" in r.text


def test_change_password_requires_session(client):
    r = client.get("/portal/account/password", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"].endswith("/portal/login")


# --------------------------------------------------------------------------- #
# Fluxo autenticado
# --------------------------------------------------------------------------- #
def test_dashboard_renders_analytics(client, onboarded_account):
    login = client.post("/portal/login", data={"email": "dev@example.com", "password": VALID_PW})
    assert login.status_code == 200

    dash = client.get("/portal/dashboard")
    assert dash.status_code == 200
    # Seção de BI e KPIs presentes no painel redesenhado.
    assert "Chamadas de API no mês" in dash.text
    assert "Taxa de sucesso" in dash.text
    assert "Painel &amp; Analytics" in dash.text or "Painel & Analytics" in dash.text


def test_change_password_flow(client, onboarded_account):
    client.post("/portal/login", data={"email": "dev@example.com", "password": VALID_PW})

    page = client.get("/portal/account/password")
    assert page.status_code == 200
    assert "Trocar senha" in page.text

    # Senha atual errada → erro.
    bad = client.post(
        "/portal/account/password",
        data={
            "current_password": "errada-000000",
            "new_password": "NovaSenha456",
            "confirm_password": "NovaSenha456",
        },
    )
    assert bad.status_code == 400

    # Troca válida → confirmação.
    ok = client.post(
        "/portal/account/password",
        data={
            "current_password": VALID_PW,
            "new_password": "NovaSenha456",
            "confirm_password": "NovaSenha456",
        },
    )
    assert ok.status_code == 200
    assert "sucesso" in ok.text.lower()


def test_change_password_confirmation_mismatch(client, onboarded_account):
    client.post("/portal/login", data={"email": "dev@example.com", "password": VALID_PW})
    r = client.post(
        "/portal/account/password",
        data={
            "current_password": VALID_PW,
            "new_password": "NovaSenha456",
            "confirm_password": "OutraCoisa789",
        },
    )
    assert r.status_code == 400
    assert "confirmação" in r.text.lower()
