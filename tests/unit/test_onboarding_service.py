"""
Regras de domínio do onboarding do portal (catálogo fixo, ordem e conclusão).

Cobre validação de slugs, seleção única vs. múltipla, bloqueio de pulo de
etapas e a marcação de ``completed_at`` ao responder a última pergunta.
"""

import pytest
from app.services import onboarding_service


def test_catalogo_tem_cinco_perguntas_sequenciais():
    assert onboarding_service.TOTAL_STEPS == 5
    assert [q.step for q in onboarding_service.QUESTIONS] == [1, 2, 3, 4, 5]
    # exatamente uma pergunta de múltipla escolha (etapas da BNCC)
    multiplas = [q for q in onboarding_service.QUESTIONS if q.multiple]
    assert [q.field for q in multiplas] == ["etapas"]


def test_get_question_fora_da_faixa():
    with pytest.raises(ValueError):
        onboarding_service.get_question(0)
    with pytest.raises(ValueError):
        onboarding_service.get_question(6)


@pytest.mark.asyncio
async def test_get_or_create_profile_idempotente(db_session, verified_account):
    p1 = await onboarding_service.get_or_create_profile(db_session, verified_account.id)
    p2 = await onboarding_service.get_or_create_profile(db_session, verified_account.id)
    assert p1.id == p2.id
    assert onboarding_service.first_pending_step(p1) == 1
    assert not onboarding_service.is_complete(p1)


@pytest.mark.asyncio
async def test_save_answer_valido_avanca(db_session, verified_account):
    profile = await onboarding_service.get_or_create_profile(db_session, verified_account.id)
    await onboarding_service.save_answer(db_session, profile, 1, ["dev"])
    assert profile.role == "dev"
    assert onboarding_service.first_pending_step(profile) == 2


@pytest.mark.asyncio
async def test_save_answer_slug_invalido(db_session, verified_account):
    profile = await onboarding_service.get_or_create_profile(db_session, verified_account.id)
    with pytest.raises(ValueError):
        await onboarding_service.save_answer(db_session, profile, 1, ["hacker'--"])


@pytest.mark.asyncio
async def test_save_answer_vazio(db_session, verified_account):
    profile = await onboarding_service.get_or_create_profile(db_session, verified_account.id)
    with pytest.raises(ValueError):
        await onboarding_service.save_answer(db_session, profile, 1, [])


@pytest.mark.asyncio
async def test_save_answer_unica_rejeita_multiplos(db_session, verified_account):
    profile = await onboarding_service.get_or_create_profile(db_session, verified_account.id)
    with pytest.raises(ValueError):
        await onboarding_service.save_answer(db_session, profile, 1, ["dev", "educador"])


@pytest.mark.asyncio
async def test_save_answer_nao_pula_etapas(db_session, verified_account):
    profile = await onboarding_service.get_or_create_profile(db_session, verified_account.id)
    with pytest.raises(ValueError):
        await onboarding_service.save_answer(db_session, profile, 3, ["app_ia"])


@pytest.mark.asyncio
async def test_fluxo_completo_marca_conclusao(db_session, verified_account):
    profile = await onboarding_service.get_or_create_profile(db_session, verified_account.id)
    respostas = {
        1: ["dev"],
        2: ["escola_rede"],
        3: ["planejamento_aulas"],
        4: ["educacao_infantil", "computacao"],
        5: ["producao"],
    }
    for step, values in respostas.items():
        await onboarding_service.save_answer(db_session, profile, step, values)

    assert onboarding_service.is_complete(profile)
    assert onboarding_service.first_pending_step(profile) is None
    assert profile.etapas == "educacao_infantil,computacao"
    # revisão de passo anterior continua permitida e preserva a conclusão
    await onboarding_service.save_answer(db_session, profile, 1, ["educador"])
    assert profile.role == "educador"
    assert onboarding_service.is_complete(profile)


@pytest.mark.asyncio
async def test_saved_values_pre_marca_multipla(db_session, verified_account):
    profile = await onboarding_service.get_or_create_profile(db_session, verified_account.id)
    question = onboarding_service.get_question(4)
    assert onboarding_service.saved_values(profile, question) == []
    for step, values in ((1, ["dev"]), (2, ["edtech"]), (3, ["app_ia"])):
        await onboarding_service.save_answer(db_session, profile, step, values)
    await onboarding_service.save_answer(db_session, profile, 4, ["ensino_medio", "computacao"])
    assert onboarding_service.saved_values(profile, question) == ["ensino_medio", "computacao"]
