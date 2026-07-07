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
python scripts/freeze_openapi.py                 # congela OpenAPI ao vivo (release lida do registro) em docs/openapi/{slug}/{release}.json
python scripts/freeze_openapi.py --check          # valida que o release congelado casa com o schema ao vivo
pre-commit run --all-files             # portões locais (segredos, lint, format)
```

## Documentação versionada (ver `docs/versioning.md`)
Dois eixos, app FastAPI único (sem sub-apps: `dependency_overrides` não se propaga a sub-apps montados).
**Eixo 1 (contratos que coexistem):** registro em `app/api/versions.py` dirige docs/OpenAPI por versão;
cada versão maior sob prefixo estável (`/api/v1`, futuro `/api/v2`). Superfícies: `/docs/{slug}` (Scalar;
`/docs` = a mais recente), `GET /api/{slug}/openapi.json`, manifesto em `GET /api/versions`. **Eixo 2
(histórico de releases):** `scripts/freeze_openapi.py` congela o OpenAPI enriquecido em
`docs/openapi/{slug}/{release}.json` (manifesto `index.json`), servido em
`GET /api/{slug}/releases/{release}/openapi.json`; Scalar navega releases via `/docs/{slug}?release=X`.
OpenAPI enriquecido montado em `app/api/openapi.py`. Adicionar v2 = incluir o roteador com
`prefix="/api/v2"` em `app/main.py` + registrar `APIVersion("v2", ...)` em `app/api/versions.py` (docs,
OpenAPI e snapshots passam a cobri-la automaticamente). **Nunca quebrar contrato dentro de uma versão
publicada — mudança incompatível exige nova versão de caminho** (Princípio I).

> **Fontes da BNCC (as 3 etapas cobertas):** EF e EM vêm de `data/bncc_ensino_fundamental.pdf` e
> `data/bncc_ensino_medio.pdf` (pdfplumber, isolamento de coluna). A **Educação Infantil** vem do
> documento oficial completo `data/BNCC_20dez_site.pdf` (472 págs.): como seu page tree comprimido
> impede o pdfplumber, o script o **normaliza com pikepdf** antes de extrair as 3 colunas de faixa
> etária. O **Complemento de Computação** (Parecer CNE/CP 02/2022) vem de
> `data/BNCCComputaoCompletodiagramado (1).pdf` via `scripts/extract_bncc_computacao.py` (chamado por
> `extract_bncc_data.py`): recupera espaços posicionais com `x_tolerance`, isola a coluna HABILIDADE
> e lê o **eixo** (horizontal na EI; rotacionado 90° no EF). Contagens atuais do snapshot: EI 104,
> EF 1408, EM 205 — inclui **141 habilidades de Computação** (`componente=computacao`), com eixos
> em EI/EF (`missing_sources: []`). Ver `specs/002-bncc-computacao/`. Os PDFs são grandes e ficam
> fora do versionamento (`data/` no .gitignore); apenas `data/bncc_v1.json` é versionado.
>
> **Reconciliação de fidelidade (auditoria 2026-07-06):** as descrições foram cruzadas com DUAS
> testemunhas do texto oficial — o documento `data/BNCC_EI_EF_110518_versaofinal_site.pdf` (600 págs.,
> normalizado com pikepdf; EI+EF+EM, o **árbitro**) e o dataset `github.com/dfdb76/bncc-mcp` (CSVs da
> versão final homologada, que casam 100% com o PDF nos códigos EI+EF). Isso corrigiu 59 descrições
> corrompidas por interleaving de coluna / truncamento / bleed e inseriu `EF05CO11` (antes ausente),
> via `scripts/reconcile_bncc_descriptions.py` + `scripts/bncc_description_fixes.json` (idempotente,
> texto oficial de livre uso, Lei 9.610/98 art. 8º IV). **Cuidado:** a seção de EM do PDF é o rascunho
> de mai/2018 (pré-homologação de dez/2018) — o EM final vem do snapshot/CSV, nunca do PDF.
>
> **Qualidade das descrições** é auditada por `scripts/audit_extraction.py` (portão versionado,
> `tests/contract/test_audit_extraction.py`): checa truncamento/blob/contaminação/fusão/**interleaving**
> (duplicação adjacente de >=4 palavras, assinatura do splice de coluna) além de códigos e contagens.
> Estado atual: **0 achados ERROR**. Habilidades de anos combinados
> (12/35/67/89) têm célula **mesclada** (largura total) recuperada por `recover_descriptions`;
> objetos com prosa de campo/exemplo são descartados (`_is_rel_bleed`). Computação traz o EF em
> dois quadros oficiais (por ano `EF0xCO` + por etapa `EF15CO`/`EF69CO`) — texto repetido entre
> esquemas é fiel, não duplicata.
