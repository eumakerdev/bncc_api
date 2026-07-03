# BNCC API — Agent Context

API pública que expõe **toda** a Base Nacional Comum Curricular (BNCC) do Brasil, com controle de
acesso self-service, documentação automática, busca semântica com IA e landing page SEO. Governado
pela Constituição em `.specify/memory/constitution.md` (v1.0.0) — **estabilidade, correção e
confiança acima de conveniência**.

## Stack (canônica — mudanças estruturais exigem emenda à Constituição)
- **Python 3.11+ · FastAPI · Pydantic v2** (pydantic-settings)
- **Dados oficiais BNCC**: snapshot estático versionado em JSON (`data/bncc_v1.json`), read-only em runtime
- **Vetores/IA**: ChromaDB + sentence-transformers/LangChain (RAG); LLM opcional (OpenAI/Google)
- **Plataforma (contas/keys/uso)**: SQLAlchemy 2.0 async + Alembic (SQLite dev → Postgres prod)
- **Superfícies visuais**: Jinja2 + Tailwind (SSR: landing + portal); docs via OpenAPI gerado
- **Auth**: portal e-mail+senha (Argon2) + verificação de e-mail + JWT; API por API keys (Bearer, hasheadas)
- **Testes**: pytest + pytest-asyncio + httpx; cobertura ≥ 80%. Lint: ruff + black; mypy em código novo

## Arquitetura em camadas (Princípio II — dependências apontam para dentro)
`app/api` (roteadores, sem regra de negócio) → `app/services` (domínio, sem objetos HTTP) →
`app/models`/dados. Infra externa (ChromaDB, LLM, DB, e-mail) só via serviços injetáveis em
`app/core/deps.py`. Config em `Settings` + variáveis de ambiente; **sem segredos hardcoded**.

## Princípios não-negociáveis (resumo)
- **I. Contrato primeiro**: API sob `/api/v1`; todo endpoint tipado com Pydantic e no OpenAPI; sem quebra dentro da versão
- **III. Testes primeiro**: contrato por endpoint; regressão em cada bugfix; cobertura ≥ 80%
- **IV. Fidelidade da BNCC**: extração determinística/versionada/reproduzível; derivados (embeddings/resumos) marcados como não-oficiais
- **V. Segurança por padrão**: `SECRET_KEY`/`ALLOWED_HOSTS` **sem defaults inseguros** — app falha rápido em produção; input validado/sanitizado; erros sem stack trace
- **VII. Determinismo sobre IA**: recursos determinísticos independem do LLM (degradação graciosa); saídas de IA validadas, limitadas em custo, nunca expostas como oficiais

## Feature ativa
`001-public-api-platform` — ver `specs/001-public-api-platform/` (spec, plan, research, data-model,
contracts, quickstart). Estado atual do repo: protótipo com ~11 habilidades de amostra; o v1 substitui
por extração exaustiva das três etapas (EI/EF/EM) e adiciona P2–P5.

## Comandos
```bash
uvicorn app.main:app --reload          # subir API (landing /, docs /guia + /docs, portal /portal)
pytest --cov=app --cov-report=term-missing   # testes + cobertura (gate ≥ 80%)
ruff check app/ scripts/ tests/ && black app/ scripts/ tests/   # lint/format
mypy app/                              # tipos (código novo; ver pyproject)
alembic upgrade head                   # migrações do banco da plataforma (contas/keys/uso)
python scripts/extract_bncc_data.py --validate   # (re)gerar snapshot data/bncc_v1.json
python scripts/validate_bncc_coverage.py         # validar cobertura/integridade do snapshot
python scripts/generate_embeddings.py            # (re)gerar vetores (opcional; requer libs de IA)
pre-commit run --all-files             # portões locais (segredos, lint, format)
```

> **Fonte da Educação Infantil (T024 — pendente):** `data/` contém apenas os PDFs de EF e EM. A
> extração cobre as três etapas, mas sem a fonte oficial da EI o snapshot registra
> `educacao_infantil: 0` e `missing_sources: ["educacao_infantil"]` — **não** se fabricam dados de EI
> (Princípio IV). Ao obter a fonte oficial da EI, coloque-a em `data/` e rode a extração novamente.
