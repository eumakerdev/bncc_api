"""
Serviço de onboarding do portal (perfil de uso pós-login).

Catálogo fixo de 5 perguntas de valor para o projeto — perfil, contexto, caso
de uso, etapas de interesse e estágio do projeto. As respostas são slugs
fechados (sem texto livre), validados aqui na fronteira de domínio (Princípio V);
a camada web apenas apresenta uma pergunta por vez e converte ``ValueError``
em re-render com mensagem amigável (Princípio II — sem objetos HTTP aqui).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.tables import OnboardingProfile

_MULTI_SEPARATOR = ","


@dataclass(frozen=True)
class OnboardingOption:
    value: str
    label: str
    description: str = ""


@dataclass(frozen=True)
class OnboardingQuestion:
    step: int
    field: str  # coluna correspondente em OnboardingProfile
    title: str
    subtitle: str
    multiple: bool
    options: tuple[OnboardingOption, ...]

    def allowed_values(self) -> set[str]:
        return {option.value for option in self.options}


QUESTIONS: tuple[OnboardingQuestion, ...] = (
    OnboardingQuestion(
        step=1,
        field="role",
        title="Qual perfil descreve melhor você?",
        subtitle="Assim conseguimos preparar guias e exemplos na sua medida.",
        multiple=False,
        options=(
            OnboardingOption("dev", "Desenvolvedor(a)", "Escrevo código e integro APIs."),
            OnboardingOption(
                "educador", "Educador(a)", "Dou aulas ou atuo em coordenação pedagógica."
            ),
            OnboardingOption(
                "produto_gestao", "Produto ou gestão", "Lidero produto/negócio em edtech."
            ),
            OnboardingOption(
                "pesquisa_estudante", "Pesquisa ou estudo", "Pesquiso ou estudo educação/dados."
            ),
        ),
    ),
    OnboardingQuestion(
        step=2,
        field="org_context",
        title="Onde a BNCC API vai ser usada?",
        subtitle="O contexto nos ajuda a priorizar recursos e limites adequados.",
        multiple=False,
        options=(
            OnboardingOption("edtech", "Empresa ou edtech", "Produto comercial de educação."),
            OnboardingOption(
                "escola_rede", "Escola ou rede de ensino", "Uso interno em instituição de ensino."
            ),
            OnboardingOption(
                "setor_publico", "Setor público", "Secretarias, órgãos ou programas de governo."
            ),
            OnboardingOption(
                "pessoal_academico", "Projeto pessoal ou acadêmico", "Estudo, TCC, pesquisa, hobby."
            ),
        ),
    ),
    OnboardingQuestion(
        step=3,
        field="use_case",
        title="O que você pretende construir primeiro?",
        subtitle="Vale escolher o mais próximo — dá para mudar de ideia depois.",
        multiple=False,
        options=(
            OnboardingOption(
                "planejamento_aulas", "Planejamento de aulas", "Planos, currículo e sequências."
            ),
            OnboardingOption(
                "sistema_escolar", "Sistema escolar ou LMS", "Diário, boletim, plataformas."
            ),
            OnboardingOption(
                "app_ia", "Aplicação com IA", "Busca semântica, chatbot, RAG sobre a BNCC."
            ),
            OnboardingOption(
                "analise_dados", "Análise de dados", "Relatórios, dashboards, pesquisa."
            ),
        ),
    ),
    OnboardingQuestion(
        step=4,
        field="etapas",
        title="Quais etapas da BNCC interessam?",
        subtitle="Pode marcar mais de uma.",
        multiple=True,
        options=(
            OnboardingOption("educacao_infantil", "Educação Infantil", "Creche e pré-escola."),
            OnboardingOption("ensino_fundamental", "Ensino Fundamental", "Do 1º ao 9º ano."),
            OnboardingOption("ensino_medio", "Ensino Médio", "Áreas e itinerários."),
            OnboardingOption("computacao", "Complemento de Computação", "Parecer CNE/CP 02/2022."),
        ),
    ),
    OnboardingQuestion(
        step=5,
        field="project_stage",
        title="Em que estágio está o seu projeto?",
        subtitle="Última pergunta — prometido!",
        multiple=False,
        options=(
            OnboardingOption("explorando", "Só explorando", "Conhecendo a API, sem projeto ainda."),
            OnboardingOption("prototipo", "Protótipo ou MVP", "Validando uma ideia."),
            OnboardingOption(
                "producao_breve", "Produção em breve", "Lançamento nos próximos meses."
            ),
            OnboardingOption("producao", "Já em produção", "Com usuários reais hoje."),
        ),
    ),
)

TOTAL_STEPS = len(QUESTIONS)


def _now() -> datetime:
    return datetime.now(UTC)


def get_question(step: int) -> OnboardingQuestion:
    """Retorna a pergunta do passo (1-indexado); ``ValueError`` se fora da faixa."""
    if not 1 <= step <= TOTAL_STEPS:
        raise ValueError(f"Passo inválido: {step}")
    return QUESTIONS[step - 1]


async def get_or_create_profile(session: AsyncSession, account_id: str) -> OnboardingProfile:
    """Busca o perfil de onboarding da conta, criando-o vazio na primeira visita."""
    result = await session.execute(
        select(OnboardingProfile).where(OnboardingProfile.account_id == account_id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = OnboardingProfile(account_id=account_id)
        session.add(profile)
        await session.commit()
        await session.refresh(profile)
    return profile


def is_complete(profile: OnboardingProfile) -> bool:
    return profile.completed_at is not None


def first_pending_step(profile: OnboardingProfile) -> int | None:
    """Primeiro passo sem resposta, ou ``None`` quando todas foram respondidas."""
    for question in QUESTIONS:
        if getattr(profile, question.field) is None:
            return question.step
    return None


def saved_values(profile: OnboardingProfile, question: OnboardingQuestion) -> list[str]:
    """Respostas já gravadas para a pergunta (para pré-marcar ao revisitar)."""
    raw: str | None = getattr(profile, question.field)
    return raw.split(_MULTI_SEPARATOR) if raw else []


async def save_answer(
    session: AsyncSession, profile: OnboardingProfile, step: int, values: list[str]
) -> None:
    """
    Valida e grava a resposta de um passo; marca a conclusão no último.

    Regras: só é possível responder passos já liberados (releitura de passos
    anteriores é permitida; pular à frente, não); toda opção deve pertencer ao
    catálogo; pergunta única aceita exatamente 1 valor, múltipla aceita 1+.
    Levanta ``ValueError`` com mensagem amigável em caso de violação.
    """
    question = get_question(step)

    pending = first_pending_step(profile)
    if pending is not None and step > pending:
        raise ValueError("Responda as perguntas na ordem — sem pular etapas.")

    # dedupe preservando a ordem de marcação
    cleaned = list(dict.fromkeys(v.strip() for v in values if v.strip()))
    if not cleaned:
        raise ValueError("Escolha uma opção para continuar.")
    if not question.multiple and len(cleaned) != 1:
        raise ValueError("Escolha apenas uma opção.")
    invalid = [v for v in cleaned if v not in question.allowed_values()]
    if invalid:
        raise ValueError("Escolha uma das opções apresentadas.")

    setattr(profile, question.field, _MULTI_SEPARATOR.join(cleaned))
    if first_pending_step(profile) is None and profile.completed_at is None:
        profile.completed_at = _now()
    await session.commit()
    await session.refresh(profile)
