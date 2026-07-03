# Implementation Plan: Plataforma Pública da BNCC API

**Branch**: `001-public-api-platform` | **Date**: 2026-07-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-public-api-platform/spec.md`

## Summary

Transformar a BNCC API (hoje um protótipo com ~11 habilidades de amostra) em um produto público v1.
O trabalho tem cinco frentes priorizadas: (P1) extração exaustiva, determinística e versionada de
**toda** a BNCC das três etapas a partir das fontes oficiais, modelada fielmente na taxonomia oficial;
(P2) controle de acesso self-service com contas de desenvolvedor (e-mail + senha, verificação de
e-mail), API keys e rate limiting com cotas separadas (60 req/min determinístico; ~20 req/min + teto
diário para IA); (P3) documentação interativa gerada automaticamente do contrato OpenAPI; (P4) busca
semântica com IA que sempre cita fontes oficiais e degrada graciosamente; (P5) landing page
SEO-first. Todas as superfícies adotam um design sofisticado e minimalista.

**Abordagem técnica**: manter a stack canônica (Python 3.11+, FastAPI, Pydantic v2, ChromaDB) e um
**único serviço** que serve a API REST versionada (`/api/v1`), as páginas server-rendered (landing +
portal do desenvolvedor) via Jinja2 + Tailwind, e a documentação interativa via OpenAPI. Adiciona-se
um armazenamento relacional (SQLite via SQLAlchemy 2.0 async + Alembic) para contas, API keys e
métricas de uso — a única adição estrutural, justificada pelo requisito novo de P2. Corrige-se o
desalinhamento de segurança com a Constituição (Princípio V): `SECRET_KEY` e `ALLOWED_HOSTS` deixam de
ter padrões inseguros e a aplicação falha rápido em produção com configuração insegura.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: FastAPI, Pydantic v2 + pydantic-settings, SQLAlchemy 2.0 (async) + Alembic,
ChromaDB, sentence-transformers/LangChain (RAG), Jinja2 + Tailwind CSS (superfícies visuais), pdfplumber
(extração de PDF), passlib[argon2]/argon2-cffi (hash de senha), PyJWT (sessão do portal), aiosmtplib
(envio de e-mail), slowapi/limite próprio para rate limiting.

**Storage**:
- **BNCC (dados oficiais)**: snapshot estático versionado em JSON (`data/bncc_v*.json`) — somente
  leitura em runtime (FR-003).
- **Vetores**: ChromaDB persistente (embeddings derivados, claramente distinguíveis dos dados oficiais).
- **Plataforma (contas, keys, uso)**: SQLite via SQLAlchemy async em dev; caminho migrável para
  PostgreSQL em produção sem mudança de código de domínio.

**Testing**: pytest + pytest-asyncio + httpx (contrato/integração), pytest-cov (cobertura ≥ 80%).
Testes de contrato validam status/schema/erro de cada endpoint público.

**Target Platform**: Servidor Linux (contêiner Docker), instância única em v1.

**Project Type**: Web service monolítico (API REST + páginas server-rendered no mesmo processo FastAPI).

**Performance Goals**: endpoints determinísticos p95 < 300 ms sob carga nominal (Constituição); landing
page Lighthouse ≥ 90 em SEO/acessibilidade/performance (SC-008); busca semântica com timeout e teto de
tokens explícitos.

**Constraints**: nenhuma configuração insegura padrão pode subir em produção (FR-023/SC-010); IA é
camada aumentada e opcional — sua indisponibilidade não pode degradar recursos determinísticos
(FR-018/SC-009); respostas de erro não vazam detalhes internos (FR-024); dados oficiais imutáveis em
runtime (snapshot versionado).

**Scale/Scope**: cobertura de ~1.700+ habilidades reais das três etapas (hoje ~11 de amostra);
tier único gratuito; centenas a milhares de desenvolvedores cadastrados; instância única com rate
limiting por key.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Avaliação | Conformidade |
|-----------|-----------|--------------|
| **I. Contrato Primeiro & Versionamento** | API sob `/api/v1`; todo endpoint com schema Pydantic tipado e presente no OpenAPI gerado; docs interativas automáticas (P3). Sem quebra dentro da versão publicada. | ✅ PASS |
| **II. Arquitetura em Camadas & DI** | Mantém `app/api` → `app/services` → `app/models`/dados; novas dependências (DB relacional, e-mail, LLM) atrás de serviços injetáveis via `app/core/deps.py`; nenhum acesso direto a infra em handlers. | ✅ PASS |
| **III. Testes em Primeiro Lugar** | Testes de contrato por endpoint, unitários de serviço, integração de auth/rate-limit; cobertura ≥ 80%; regressão para o bug de config insegura (FR-023). | ✅ PASS (gate de CI) |
| **IV. Fidelidade dos Dados da BNCC** | Extração determinística/versionada/reproduzível dos PDFs; validação de completude e integridade contra a fonte; campos derivados (embeddings/resumos) marcados como não-oficiais. | ✅ PASS |
| **V. Segurança por Padrão** | **Corrige o desalinhamento atual**: remove `SECRET_KEY` padrão e `ALLOWED_HOSTS=["*"]`; valida config na inicialização (fail-fast em produção); input validado/sanitizado; rate limiting ativo; segredos via ambiente; erros sem stack trace. | ✅ PASS (endereça FR-023) |
| **VI. Observabilidade & Operabilidade** | Logging estruturado sem PII/segredos; health/readiness refletindo DB + ChromaDB; falhas de LLM/embedding tratadas com erro acionável (nunca 500 opaco). | ✅ PASS |
| **VII. Simplicidade & Determinismo sobre IA** | Recursos determinísticos independem do LLM (degradação graciosa); saídas de IA validadas, limitadas em custo e nunca expostas como oficiais; adota-se a solução mais simples (monolito + SQLite + SSR) evitando SPA/Redis em v1. | ✅ PASS |

**Adições estruturais avaliadas** (Constituição exige justificativa — ver *Complexity Tracking*):
armazenamento relacional (contas/keys/uso), motor de templates (superfícies visuais) e serviço de
e-mail. São **adições** requeridas por P2/P3/P5, não substituições da stack canônica → permitidas.
Nenhuma viola um princípio; nenhuma exige emenda à Constituição.

**Resultado do gate**: ✅ PASS (inicial e pós-desenho). Sem violações não justificadas.

## Project Structure

### Documentation (this feature)

```text
specs/001-public-api-platform/
├── plan.md              # Este arquivo (/speckit-plan)
├── research.md          # Fase 0 — decisões técnicas
├── data-model.md        # Fase 1 — entidades de domínio e plataforma
├── quickstart.md        # Fase 1 — guia de validação executável
├── contracts/           # Fase 1 — contratos de API por área
│   ├── README.md
│   ├── bncc-data.md
│   ├── auth-portal.md
│   ├── api-keys-usage.md
│   └── semantic-search.md
└── tasks.md             # Fase 2 (/speckit-tasks — NÃO criado aqui)
```

### Source Code (repository root)

Estende a estrutura existente (monolito FastAPI). Novos diretórios em **negrito**.

```text
app/
├── main.py                      # App FastAPI: monta API, páginas e docs; fail-fast de config
├── core/
│   ├── config.py                # Settings — remover padrões inseguros; validação de produção
│   ├── deps.py                  # DI: DB session, serviços, auth por API key, rate limiter
│   ├── security.py  (novo)      # hash de senha, JWT de sessão, geração/hash de API key
│   └── errors.py    (novo)      # handlers de erro que não vazam detalhes internos
├── api/
│   └── v1/
│       ├── api.py               # agrega routers da v1
│       └── endpoints/
│           ├── habilidades.py         # existente (expandido: relações navegáveis)
│           ├── competencias.py        # existente (geral/específica + EI/EM)
│           ├── busca.py               # busca semântica (cota IA separada, fontes)
│           ├── sistema.py             # health/readiness/estatísticas/versão de dados
│           ├── auth.py        (novo)  # signup, verificação de e-mail, login
│           ├── keys.py        (novo)  # criar/listar/revogar API keys
│           └── usage.py       (novo)  # métricas de uso por key
├── models/
│   ├── bncc.py                  # Pydantic de domínio (expandido: EI, EM, relações)
│   └── platform.py  (novo)      # Pydantic de conta/key/uso (schemas de request/response)
├── db/               (novo)
│   ├── base.py                  # engine/session async SQLAlchemy
│   └── tables.py                # tabelas ORM: contas, keys, uso, tokens de verificação
├── services/
│   ├── bncc_service.py          # existente (leitura do snapshot; relações)
│   ├── vector_store.py          # existente (embeddings/ChromaDB)
│   ├── ai_service.py            # existente (RAG; fallback determinístico, limites de custo)
│   ├── account_service.py (novo)# contas + verificação de e-mail
│   ├── apikey_service.py  (novo)# ciclo de vida e autenticação de keys
│   ├── usage_service.py   (novo)# contabilização e rate limiting (cotas dupla)
│   └── email_service.py   (novo)# envio de e-mail (SMTP; backend console em dev)
├── web/              (novo)      # superfícies server-rendered (SSR)
│   ├── router.py                # rotas de páginas (landing, portal, docs)
│   ├── templates/               # Jinja2 (design minimalista comum)
│   │   ├── base.html
│   │   ├── landing.html         # SEO: meta, OG, JSON-LD, sitemap
│   │   ├── portal/              # dashboard, keys, uso, login/signup
│   │   └── docs.html            # docs interativa (embute OpenAPI)
│   └── static/                  # CSS (Tailwind build), ícones, OG image
└── utils/
    └── helpers.py               # existente

migrations/          (novo)      # Alembic (contas/keys/uso)
scripts/
├── extract_bncc_data.py         # REESCRITO: extração real e determinística dos PDFs + EI
├── generate_embeddings.py       # existente (regenera vetores do snapshot)
└── validate_bncc_coverage.py (novo)  # valida cobertura/integridade vs fonte oficial
data/
├── bncc_v1.json     (novo)      # snapshot versionado (substitui a amostra)
├── bncc_ensino_fundamental.pdf  # fonte oficial (presente)
├── bncc_ensino_medio.pdf        # fonte oficial (presente)
└── chromadb/                    # vetores persistidos
tests/
├── contract/         (novo)     # testes de contrato por endpoint público
├── integration/      (novo)     # signup→verificação→key→chamada; rate limit; degradação de IA
└── unit/             (novo)     # serviços (auth, keys, uso, parsing de extração)
```

**Structure Decision**: **Web service monolítico** (Project Type: web service). Um único processo
FastAPI serve (a) a API REST versionada, (b) as páginas server-rendered (landing + portal) via Jinja2
e (c) a documentação interativa via OpenAPI. Escolha alinhada à Constituição (stack canônica Python/
FastAPI) e ao Princípio VII (simplicidade): evita um segundo runtime/SPA e um serviço de cache
externo em v1, mantendo SEO por SSR e um único artefato de deploy. As camadas existentes
(`api → services → models`) são preservadas; a persistência relacional entra atrás de serviços
injetáveis (Princípio II). Detalhes e alternativas rejeitadas em [research.md](./research.md).

## Complexity Tracking

> Adições estruturais que a Constituição exige justificar (não são violações; são novas
> dependências requeridas por requisitos concretos de P2/P3/P5).

| Adição | Por que é necessária | Alternativa mais simples rejeitada porque |
|--------|----------------------|--------------------------------------------|
| Banco relacional (SQLAlchemy + SQLite, migrável a Postgres) | P2 exige contas, API keys e métricas de uso persistentes (FR-007..FR-011) — o snapshot JSON é read-only e imutável | Guardar contas/keys em JSON/ChromaDB: sem transações, unicidade nem consultas de uso confiáveis; inseguro para credenciais |
| Motor de templates (Jinja2 + Tailwind) no mesmo serviço | P5 (landing SEO) e P2 (portal) precisam de HTML server-rendered para SEO e para exibir keys/uso (FR-020..FR-022) | SPA separada (Next.js): novo runtime/build/deploy, viola stack canônica e YAGNI; pior TTFB para SEO em v1 |
| Serviço de e-mail (SMTP async) | Verificação de e-mail obrigatória antes de liberar keys (FR-007) | Sem verificação: contradiz a decisão de escopo confirmada e enfraquece a segurança |
| Rate limiting com cota dupla in-process/SQLite | FR-010/FR-010a exigem 60/min determinístico e ~20/min + teto diário para IA, medidos separadamente | Redis: infra extra desnecessária para instância única em v1; reservado como caminho de escala |
