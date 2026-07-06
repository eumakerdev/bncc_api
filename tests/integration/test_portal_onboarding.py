"""
Onboarding SSR do portal — wizard obrigatório pós-login, uma pergunta por vez.

Cobre o gate do dashboard/keys, a progressão passo a passo (PRG), a validação
amigável de respostas e a saída do fluxo após a conclusão.
"""

VALID_PW = "senha-forte-123"  # pragma: allowlist secret

RESPOSTAS = {
    1: ["dev"],
    2: ["edtech"],
    3: ["app_ia"],
    4: ["ensino_fundamental", "ensino_medio"],
    5: ["prototipo"],
}


def _login(client):
    r = client.post("/portal/login", data={"email": "dev@example.com", "password": VALID_PW})
    assert r.status_code == 200
    return client


def test_onboarding_requires_session(client):
    r = client.get("/portal/onboarding", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"].endswith("/portal/login")


def test_onboarding_post_requires_session(client):
    r = client.post(
        "/portal/onboarding", data={"step": 1, "resposta": "dev"}, follow_redirects=False
    )
    assert r.status_code == 303
    assert r.headers["location"].endswith("/portal/login")


def test_dashboard_redirects_to_onboarding_when_pending(client, verified_account):
    _login(client)
    r = client.get("/portal/dashboard", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/portal/onboarding"


def test_keys_post_gated_by_onboarding(client, verified_account):
    _login(client)
    r = client.post("/portal/keys", data={"name": "x"}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/portal/onboarding"


def test_onboarding_renders_first_question(client, verified_account):
    _login(client)
    r = client.get("/portal/onboarding")
    assert r.status_code == 200
    assert "Pergunta 1 de 5" in r.text
    assert "Qual perfil descreve melhor você?" in r.text


def test_onboarding_cannot_jump_ahead_via_query(client, verified_account):
    _login(client)
    r = client.get("/portal/onboarding?step=4")
    assert r.status_code == 200
    assert "Pergunta 1 de 5" in r.text  # volta para o primeiro pendente


def test_onboarding_invalid_answer_rerenders_with_error(client, verified_account):
    _login(client)
    r = client.post("/portal/onboarding", data={"step": 1, "resposta": "nao-existe"})
    assert r.status_code == 400
    assert "opções apresentadas" in r.text
    assert "Pergunta 1 de 5" in r.text


def test_onboarding_empty_multi_rerenders_with_error(client, verified_account):
    _login(client)
    for step in (1, 2, 3):
        client.post("/portal/onboarding", data={"step": step, "resposta": RESPOSTAS[step]})
    r = client.post("/portal/onboarding", data={"step": 4})
    assert r.status_code == 400
    assert "Escolha uma opção" in r.text


def test_onboarding_step_out_of_range_redirects(client, verified_account):
    _login(client)
    r = client.post(
        "/portal/onboarding", data={"step": 99, "resposta": "dev"}, follow_redirects=False
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/portal/onboarding"


def test_onboarding_full_flow_unlocks_dashboard(client, verified_account):
    _login(client)
    for step, values in RESPOSTAS.items():
        r = client.post(
            "/portal/onboarding", data={"step": step, "resposta": values}, follow_redirects=False
        )
        assert r.status_code == 303, f"passo {step} falhou"
        assert r.headers["location"] == "/portal/onboarding"

    # concluído: onboarding manda para o dashboard, que agora responde 200
    done = client.get("/portal/onboarding", follow_redirects=False)
    assert done.status_code == 303
    assert done.headers["location"] == "/portal/dashboard"
    assert client.get("/portal/dashboard").status_code == 200


def test_onboarding_back_step_allows_review(client, verified_account):
    _login(client)
    client.post("/portal/onboarding", data={"step": 1, "resposta": "dev"})
    # segunda pergunta pendente; revisitar a primeira mantém a resposta marcada
    r = client.get("/portal/onboarding?step=1")
    assert r.status_code == 200
    assert "Pergunta 1 de 5" in r.text
    assert "checked" in r.text


def test_onboarded_account_skips_wizard(client, onboarded_account):
    _login(client)
    r = client.get("/portal/onboarding", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/portal/dashboard"
    assert client.get("/portal/dashboard").status_code == 200
