---
description: "Task list for Plataforma Pública da BNCC API"
---

# Tasks: Plataforma Pública da BNCC API

**Input**: Design documents from `/specs/001-public-api-platform/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: INCLUDED — a Constituição (Princípio III "Testes em Primeiro Lugar") e a spec (gate de CI,
cobertura ≥ 80%, teste de contrato por endpoint) tornam os testes **obrigatórios** neste projeto.

**Organization**: Tasks agrupadas por user story (US1–US5) para implementação e teste independentes.

> **Remediação aplicada (análise de consistência 2026-07-03)**: adicionadas T007 (pipeline de CI,
> achado C1), T024 (obtenção da fonte da Educação Infantil, achado **HIGH** G1), T029 (auditoria de
> fidelidade de texto, achado G3) e T078 (teste de performance p95 < 300 ms, achado **HIGH** G2).
> Valores antes subespecificados (cotas, limiar, limites de IA, senha) foram fixados na spec/contratos.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependências)
- **[Story]**: US1..US5 (mapeia às histórias da spec.md)
- Caminhos de arquivo são relativos à raiz do repositório

## Path Conventions

Monolito FastAPI existente (ver plan.md → Project Structure): `app/`, `scripts/`, `tests/`, `data/`,
`migrations/` na raiz do repositório.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Preparar dependências, configuração, estrutura de diretórios e portões de CI do monolito.

- [X] T001 Atualizar `requirements.txt` com as novas dependências (SQLAlchemy 2.0 + Alembic + aiosqlite, passlib[argon2]/argon2-cffi, PyJWT, aiosmtplib, Jinja2, pdfplumber, slowapi, sentence-transformers/LangChain, ChromaDB, httpx, pytest-asyncio, pytest-cov)
- [X] T002 [P] Criar `.env.example` na raiz com todas as variáveis de config **sem defaults inseguros** (SECRET_KEY, ALLOWED_HOSTS, ENVIRONMENT, DATABASE_URL, SMTP_*, ACCESS_TOKEN_EXPIRE_MINUTES, LLM/embedding keys opcionais, limites de IA)
- [X] T003 [P] Configurar ruff + black + mypy (código novo) em `pyproject.toml`
- [X] T004 [P] Configurar pytest em `pyproject.toml`/`pytest.ini` (asyncio mode, cobertura ≥ 80% como gate)
- [X] T005 [P] Criar scaffolding de diretórios: `app/db/`, `app/web/templates/`, `app/web/static/`, `migrations/`, `tests/contract/`, `tests/integration/`, `tests/unit/`
- [X] T006 [P] Adicionar `Dockerfile` + `docker-compose.yml` na raiz (referenciados em quickstart.md)
- [X] T007 [P] Configurar pipeline de CI em `.github/workflows/ci.yml` com **portões bloqueantes** exigidos pela Constituição: suíte verde, cobertura ≥ 80%, `ruff` + `black` limpos e build da imagem Docker bem-sucedido

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Núcleo de config segura, camada de dados relacional, segurança, DI e wiring do app.

**⚠️ CRITICAL**: Bloqueia todas as histórias de backend (US1–US4). A tarefa de design compartilhado
(T017) só é pré-requisito das superfícies visuais (US2 portal, US3 docs, US5 landing), não do US1.

- [X] T008 Corrigir configuração insegura em `app/core/config.py` (FR-023): remover default de `SECRET_KEY`, restringir `ALLOWED_HOSTS` (rejeitar `*` em produção), validators de startup com fail-fast em `ENVIRONMENT=production`
- [X] T009 [P] Criar handlers de erro globais em `app/core/errors.py` (FR-024): respostas sem stack trace/paths/detalhes internos
- [X] T010 [P] Criar utilitários de segurança em `app/core/security.py`: hash Argon2 de senha, emissão/validação de JWT, geração de API key + hash SHA-256 + prefixo não sensível
- [X] T011 Configurar engine/session async do SQLAlchemy em `app/db/base.py` (SQLite dev, URL migrável a Postgres)
- [X] T012 Definir tabelas ORM em `app/db/tables.py`: `developer_accounts`, `email_verification_tokens`, `api_keys`, `usage_records` (ver data-model.md §B)
- [X] T013 Inicializar Alembic e gerar migração inicial em `migrations/` (contas/keys/uso/tokens)
- [X] T014 [P] Criar schemas Pydantic da plataforma em `app/models/platform.py` (request/response de conta, key, uso; política de senha ≥ 10 caracteres — FR-007)
- [X] T015 Atualizar container de DI em `app/core/deps.py`: provider de DB session, injeção de serviços, dependências (placeholder) de auth por API key e rate limiter
- [X] T016 Fazer o wiring de `app/main.py`: registrar handlers de erro, fail-fast de config no startup, montar API `/api/v1` e o web router
- [X] T017 [P] Design system compartilhado (FR-022): build estático do Tailwind em `app/web/static/` + `app/web/templates/base.html` + tokens minimalistas (consumido por US2/US3/US5)
- [X] T018 [P] Teste de regressão de config insegura (escrever primeiro, deve falhar) em `tests/unit/test_config_security.py` (FR-023/SC-010: app não sobe em produção com SECRET_KEY placeholder / ALLOWED_HOSTS=*)

**Checkpoint**: Fundação pronta — implementação das histórias pode começar.

---

## Phase 3: User Story 1 - Consumir a BNCC completa via API estruturada (Priority: P1) 🎯 MVP

**Goal**: Expor **toda** a BNCC das três etapas (EI/EF/EM) por endpoints determinísticos, com códigos/
textos oficiais preservados e relações navegáveis, sobre um snapshot versionado.

**Independent Test**: Consultar habilidades/competências por código oficial de cada etapa (`EF05MA07`,
`EM13MAT101`, `EI03EO01`) e por filtros paginados; conferir correspondência exata à fonte oficial e
cobertura das três etapas (`/api/v1/sistema/versao-dados` com contagens > 0). Nos testes, a dependência
de API key é sobreposta por um fixture (a autenticação real é entregue em US2).

**⚠️ Gating (achado G1)**: T024 (fonte da Educação Infantil) é **pré-requisito** de T026/T028 — sem a
fonte oficial da EI (ausente em `data/`), FR-001/SC-001 não podem ser satisfeitos.

### Tests for User Story 1 (escrever primeiro, garantir que FALHAM)

- [X] T019 [P] [US1] Teste de contrato dos endpoints de habilidades (get por código, list com filtros+paginação, relações) em `tests/contract/test_habilidades.py`
- [X] T020 [P] [US1] Teste de contrato dos endpoints de competências (gerais, gerais/{numero}, específicas) em `tests/contract/test_competencias.py`
- [X] T021 [P] [US1] Teste de contrato de `taxonomia` + `sistema/versao-dados` em `tests/contract/test_taxonomia_sistema.py`
- [X] T022 [P] [US1] Teste unitário do validador de código (EI/EF/EM) e do parsing de extração em `tests/unit/test_bncc_parsing.py`
- [X] T023 [P] [US1] Teste de integração de cobertura das três etapas em `tests/integration/test_bncc_coverage.py` (SC-001)

### Implementation for User Story 1

- [X] T024 [US1] **Obter e validar a fonte oficial da Educação Infantil** (achado G1): adquirir o PDF/fonte estruturada da EI para `data/` (hoje só há EF+EM), registrar checksum e proveniência; **gating** — bloqueia T026/T028 (FR-001/SC-001)
- [X] T025 [US1] Estender `app/models/bncc.py`: Campo de Experiência + objetivos de aprendizagem (EI), Unidade Temática, Objeto de Conhecimento (navegável), habilidades/competências do Ensino Médio, metadados do snapshot, validadores dos 3 formatos de código (data-model.md §A)
- [X] T026 [US1] Reescrever `scripts/extract_bncc_data.py`: parsing determinístico com pdfplumber, parsers por etapa (EF `EF<ano><COMP><NN>`, EM `EM13<AREA><NNN>`, EI `EI<faixa><CAMPO><NN>`) → `data/bncc_v1.json` com versão/data/checksum das fontes (FR-002/FR-003; depende de T024)
- [X] T027 [US1] Criar `scripts/validate_bncc_coverage.py`: unicidade de código, formato por etapa, integridade referencial (habilidade→competências/objetos), contagens por etapa/componente (Princípio IV)
- [X] T028 [US1] Gerar e validar o snapshot `data/bncc_v1.json` (executar T026 + T027; discrepâncias registradas como defeito de correção, não corrigidas em silêncio)
- [X] T029 [US1] **Auditoria de fidelidade de texto** (achado G3, SC-002): comparar o texto servido a uma amostra de códigos oficiais das três etapas contra o documento oficial, exigindo 100% de correspondência exata; registrar em `tests/integration/test_bncc_fidelity.py`
- [X] T030 [US1] Expandir `app/services/bncc_service.py`: carregar snapshot read-only, get-por-código, filtros + paginação, resolução de relações, árvore de taxonomia
- [X] T031 [US1] Implementar endpoints de habilidades em `app/api/v1/endpoints/habilidades.py` (`GET /habilidades/{codigo}`, `GET /habilidades`, `GET /habilidades/{codigo}/relacoes`)
- [X] T032 [US1] Implementar endpoints de competências em `app/api/v1/endpoints/competencias.py` (`/competencias/gerais`, `/competencias/gerais/{numero}`, `/competencias/especificas`)
- [X] T033 [US1] Implementar `GET /api/v1/taxonomia` e `GET /api/v1/sistema/versao-dados` em `app/api/v1/endpoints/sistema.py` (+ rota de taxonomia)
- [X] T034 [US1] Registrar routers de US1 em `app/api/v1/api.py` e mapear validação/erros (400 malformado, 404 inexistente, sem vazar internos)

**Checkpoint**: BNCC completa consultável e testável de forma independente (MVP entregável).

> **⚠️ Restrição de deploy (achado C2)**: os endpoints de US1 só recebem auth por API key e rate
> limiting em T044 (US2). **Não publicar US1 isoladamente como MVP público** sem US2 — uma superfície
> pública sem autenticação/limite viola o Princípio V e FR-009. Demos de US1 usam o override de auth
> de teste (fixture).

---

## Phase 4: User Story 2 - Acesso controlado via portal self-service e API keys (Priority: P2)

**Goal**: Cadastro por e-mail+senha com verificação obrigatória, geração/revogação de API keys,
autenticação por Bearer, rate limiting de cota dupla e métricas de uso por key.

**Independent Test**: Cadastrar → verificar e-mail → login → criar key → chamada autenticada com
sucesso; chamada sem key → 401; acima de 60/min → 429 com `Retry-After`; painel mostra consumo por key.

### Tests for User Story 2 (escrever primeiro, garantir que FALHAM)

- [X] T035 [P] [US2] Teste de contrato de auth (signup/verify-email/login/logout/me) em `tests/contract/test_auth.py`
- [X] T036 [P] [US2] Teste de contrato de keys (create/list/revoke; 403 se não verificado) em `tests/contract/test_keys.py`
- [X] T037 [P] [US2] Teste de contrato de uso (por key + agregado da conta) em `tests/contract/test_usage.py`
- [X] T038 [P] [US2] Teste unitário do rate limiter (cota dupla: 60/min+burst 10 determinístico; 20/min + teto 500/dia de IA) em `tests/unit/test_rate_limit.py`
- [X] T039 [US2] Teste de integração do fluxo completo em `tests/integration/test_access_flow.py` (signup→verify→login→key→chamada autenticada; sem key 401; acima do limite 429)

### Implementation for User Story 2

- [X] T040 [P] [US2] Serviço de e-mail em `app/services/email_service.py` (backend de console em dev; SMTP async em produção via `aiosmtplib`)
- [X] T041 [US2] Serviço de contas em `app/services/account_service.py` (signup com senha ≥ 10 chars, verificação de e-mail por token de uso único, login, mensagens anti-enumeração)
- [X] T042 [US2] Serviço de API keys em `app/services/apikey_service.py` (criar/listar/revogar; autenticação por prefixo indexado + comparação por hash SHA-256)
- [X] T043 [US2] Serviço de uso em `app/services/usage_service.py` (contabilização, rate limiting in-process de cota dupla — 60/min+burst 10 e 20/min, teto diário de 500 durável em `usage_records`)
- [X] T044 [US2] Implementar dependências de auth por API key + rate limit em `app/core/deps.py` e aplicá-las aos endpoints de dados (e depois de IA): 401 sem key válida, 429 com `Retry-After` acima do limite (fecha a restrição de deploy do US1)
- [X] T045 [US2] Endpoints de auth em `app/api/v1/endpoints/auth.py` (signup 201, verify-email, login/logout, me)
- [X] T046 [US2] Endpoints de keys em `app/api/v1/endpoints/keys.py` (POST/GET/DELETE; segredo exibido uma única vez; 403 se e-mail não verificado)
- [X] T047 [US2] Endpoints de uso em `app/api/v1/endpoints/usage.py` (`/keys/{id}/usage` e `/usage` agregado)
- [X] T048 [US2] Registrar routers de US2 em `app/api/v1/api.py`
- [X] T049 [P] [US2] Páginas SSR do portal — login/signup em `app/web/templates/portal/` (estendendo `base.html`)
- [X] T050 [P] [US2] Páginas SSR do portal — dashboard + keys + consumo em `app/web/templates/portal/`
- [X] T051 [US2] Rotas web do portal (com sessão) em `app/web/router.py`

**Checkpoint**: Acesso self-service funcional; US1 e US2 operáveis independentemente.

---

## Phase 5: User Story 3 - Documentação interativa gerada automaticamente (Priority: P3)

**Goal**: Documentação sempre sincronizada com o contrato OpenAPI, com schemas, exemplos, teste
autenticado e guia de início rápido, no mesmo design minimalista.

**Independent Test**: Abrir a documentação e confirmar que todos os endpoints públicos aparecem com
schemas/exemplos; "testar" executa chamada real autenticada por API key; alterar um endpoint no código
reflete nas docs sem edição manual.

### Tests for User Story 3 (escrever primeiro, garantir que FALHAM)

- [X] T052 [P] [US3] Teste de integração de sincronia das docs em `tests/integration/test_docs.py` (OpenAPI lista 100% dos endpoints públicos; página de docs renderiza)

### Implementation for User Story 3

- [X] T053 [US3] Enriquecer metadados OpenAPI em todos os endpoints (descrições, exemplos, tags, schemas de erro) — FR-013/FR-014 (fora do escopo owned por US3/US5; endpoints são de US1/US2/US4)
- [X] T054 [US3] Página de docs estilizada em `app/web/templates/docs.html` embutindo o mesmo spec OpenAPI (Swagger UI com "testar" por API key)
- [X] T055 [US3] Conteúdo do guia de início rápido nas docs (autenticação, limites, versionamento) — FR-015
- [X] T056 [US3] Rota de docs em `app/web/docs.py` (`GET /guia`), incluída pelo seam de `app/web/router.py` via `include_web_routers()`

**Checkpoint**: Documentação fiel ao contrato e navegável.

---

## Phase 6: User Story 4 - Busca semântica com IA em linguagem natural (Priority: P4)

**Goal**: Responder perguntas em linguagem natural com texto gerado + fontes oficiais rastreáveis,
cota de IA separada, limites de custo, degradação graciosa e conteúdo claramente não-oficial.

**Independent Test**: Enviar pergunta válida → resposta com `fontes` (código+relevância) marcada como
não-oficial; sem match → "sem resultados confiáveis"; acima de 20/min ou teto de 500/dia → 429 no
bucket `ai`; com IA fora do ar → 503 acionável **e** endpoints determinísticos seguem 200 (SC-009).

### Tests for User Story 4 (escrever primeiro, garantir que FALHAM)

- [X] T057 [P] [US4] Teste de contrato de `busca-semantica` em `tests/contract/test_busca_semantica.py` (200 com fontes; sem-match abaixo do limiar 0,70; 400; 429 bucket ai; 503)
- [X] T058 [US4] Teste de integração de degradação de IA em `tests/integration/test_ai_degradation.py` (SC-009: IA fora → 503 na IA, determinístico 100% 200)

### Implementation for User Story 4

- [X] T059 [P] [US4] Schemas `BuscaSemanticaRequest`/`BuscaSemanticaResponse` com sanitização (3–500 chars, anti-injeção) e marcação de conteúdo não-oficial em `app/models/bncc.py` (ou módulo dedicado)
- [X] T060 [US4] Reescrever/expandir `scripts/generate_embeddings.py` (regenerar vetores a partir do snapshot versionado)
- [X] T061 [US4] Expandir `app/services/vector_store.py` (ChromaDB persistente, limiar de similaridade padrão 0,70 configurável, marcação de derivado ✳️ — FR-017)
- [X] T062 [US4] Expandir `app/services/ai_service.py` (RAG, timeout de 15 s + teto de 800 tokens de saída, fallback gracioso, citação de fontes, tratamento de ausência de match — FR-016..FR-019)
- [X] T063 [US4] Endpoint `POST /api/v1/busca-semantica` em `app/api/v1/endpoints/busca.py` (rate limit no bucket `ai`: 20/min + 500/dia, 503 acionável)
- [X] T064 [US4] `readiness` distinguindo "IA indisponível" de "serviço fora" em `app/api/v1/endpoints/sistema.py` (Princípio VI)
- [X] T065 [US4] Registrar router de US4 em `app/api/v1/api.py`

**Checkpoint**: Busca semântica funcional e isolada; determinístico intacto sob falha de IA.

---

## Phase 7: User Story 5 - Landing page com SEO (Priority: P5)

**Goal**: Landing pública sofisticada e minimalista com proposta de valor, recursos, público-alvo, CTA
e metadados de SEO completos, atingindo Lighthouse ≥ 90.

**Independent Test**: Carregar `/` e confirmar proposta de valor + CTA; presença de meta tags, Open
Graph, JSON-LD, `/sitemap.xml`, `/robots.txt`; Lighthouse ≥ 90 em SEO/acessibilidade/performance.

### Tests for User Story 5 (escrever primeiro, garantir que FALHAM)

- [X] T066 [P] [US5] Teste de integração de SEO da landing em `tests/integration/test_landing.py` (meta/OG/JSON-LD, `/sitemap.xml`, `/robots.txt`, HTML semântico)

### Implementation for User Story 5

- [X] T067 [US5] Template `app/web/templates/landing.html` (proposta de valor, recursos, público-alvo, CTA para cadastro/docs)
- [X] T068 [US5] Metadados de SEO na landing (title/description/Open Graph/JSON-LD) + asset de OG image em `app/web/static/`
- [X] T069 [US5] Rotas `/sitemap.xml` e `/robots.txt` em `app/web/landing.py`, incluídas pelo seam de `app/web/router.py` via `include_web_routers()`
- [X] T070 [US5] Rota da landing (`GET /`) em `app/web/landing.py`, incluída pelo seam de `app/web/router.py` via `include_web_routers()`
- [X] T071 [P] [US5] Consolidar tokens/estilos minimalistas compartilhados entre landing/portal/docs (FR-022) — já entregue em `app/web/static/styles.css` (T017); reutilizado (`.container`, `.hero`, `.lead`, `.grid`, `.card`, `.btn`, `.section`, `.badge`) sem duplicação
- [X] T072 [US5] Ajuste de performance/acessibilidade para Lighthouse ≥ 90 (sem JS pesado; SC-008) — sem JS nas páginas, CSS estático único, `<meta viewport>`, `skip-link`, headings semânticos únicos, sem CDN externo

**Checkpoint**: Todas as histórias entregues e independentemente funcionais.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Fechamento de qualidade, observabilidade, segurança, performance e validação ponta a ponta.

- [X] T073 [P] Garantir cobertura ≥ 80% (`pytest --cov=app --cov-report=term-missing`) e preencher lacunas em `tests/unit/`
- [X] T074 [P] Rodar ruff + black + mypy no código novo e corrigir apontamentos
- [X] T075 [P] Logging estruturado sem PII/segredos (Princípio VI) nos serviços (nunca logar senha/hash/token/key/e-mail)
- [X] T076 Health/readiness refletindo DB + ChromaDB em `app/api/v1/endpoints/sistema.py`
- [X] T077 [P] Atualizar `README`/`CLAUDE.md` com novos comandos (migrações, validação de cobertura, fonte da EI)
- [X] T078 **Teste de performance** (achado G2, SC-005): smoke de carga nos endpoints determinísticos assertando **p95 < 300 ms** sob carga nominal em `tests/integration/test_performance.py` (ou script equivalente)
- [X] T079 Rodar a validação ponta a ponta do `quickstart.md` (Cenários 1–6)
- [X] T080 [P] Revisão de segurança (anti-enumeração, não vazamento de erro, hashing de keys/senha) — FR-023/FR-024
- [X] T081 Verificar métricas de sucesso (SC-001..SC-011) como checklist de aceite

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências — pode iniciar imediatamente.
- **Foundational (Phase 2)**: depende do Setup — BLOQUEIA US1–US4. T017 (design compartilhado) só bloqueia US2/US3/US5.
- **US1 (Phase 3)**: depende do Foundational (exceto T017). **T024 (fonte da EI) é gating** de T026/T028. MVP.
- **US2 (Phase 4)**: depende do Foundational; T044 aplica auth/rate limit aos endpoints de US1 (fecha a restrição de deploy do US1).
- **US3 (Phase 5)**: depende de US1 (endpoints a documentar) e de T017 (base.html). US2 melhora o "testar autenticado".
- **US4 (Phase 6)**: depende de US1 (snapshot) e de US2 (cota/bucket `ai` no rate limiter, T044).
- **US5 (Phase 7)**: depende de T017 (design). Apresenta o produto; independente das APIs em runtime.
- **Polish (Phase 8)**: depende das histórias desejadas concluídas.

### Critical / gating dependencies (remediação)

- **T024 → T026 → T028**: sem a fonte oficial da EI, a extração e o snapshot não cobrem as três etapas (FR-001/SC-001). Resolver T024 **antes** de iniciar a extração.
- **US1 público exige T044**: não expor endpoints de US1 sem auth/rate limit (Princípio V/FR-009).
- **T007 (CI)** deve estar ativo cedo para que os portões de cobertura/lint/Docker valham por todo o desenvolvimento.

### User Story Dependencies

- **US1 (P1)**: Foundational + T024 (EI). Núcleo; sem dependência de outras histórias.
- **US2 (P2)**: Foundational; integra com US1 (aplica auth/limite via T044), mas testável de forma independente.
- **US3 (P3)**: US1 (endpoints) + T017; independente de US4/US5.
- **US4 (P4)**: US1 (dados) + US2 (rate limit de IA).
- **US5 (P5)**: T017 (design); independente das APIs.

### Within Each User Story

- Testes escritos **antes** e devem falhar; modelos → serviços → endpoints → integração/registro.

### Parallel Opportunities

- Setup: T002–T007 em paralelo.
- Foundational: T009, T010, T014, T017, T018 em paralelo (T011→T012→T013 sequenciais; T015/T016 após).
- Todos os testes `[P]` de uma história rodam juntos; modelos/serviços em arquivos distintos `[P]` juntos.
- Após o Foundational, US1 e US2 podem ser tocadas por devs diferentes; US3/US4/US5 seguem após suas deps.

---

## Parallel Example: User Story 1

```bash
# Testes de US1 juntos (escrever primeiro, devem falhar):
Task: "Contrato de habilidades em tests/contract/test_habilidades.py"
Task: "Contrato de competências em tests/contract/test_competencias.py"
Task: "Contrato de taxonomia+sistema em tests/contract/test_taxonomia_sistema.py"
Task: "Unit do validador/parsing em tests/unit/test_bncc_parsing.py"
Task: "Integração de cobertura em tests/integration/test_bncc_coverage.py"

# Gating antes da extração:
Task: "T024 — obter/validar a fonte oficial da Educação Infantil em data/"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1: Setup (inclui CI — T007).
2. Phase 2: Foundational (crítico — inclui a correção de segurança FR-023).
3. Phase 3: US1 — **resolver T024 (fonte da EI)** → extração exaustiva + endpoints determinísticos.
4. **PARAR e VALIDAR**: consultar as três etapas por código/filtros; conferir fidelidade à fonte (T029).
5. Demo do MVP com auth de teste sobreposta — **não** publicar sem US2 (restrição C2).

### Incremental Delivery

1. Setup + Foundational → fundação pronta.
2. US1 → validar → MVP (interno).
3. US2 → acesso controlado real (auth + keys + limites, T044) → validar → publicável.
4. US3 → documentação → validar.
5. US4 → busca semântica → validar.
6. US5 → landing SEO → validar.

### Parallel Team Strategy

- Após o Foundational: Dev A em US1 (começando por T024); Dev B começa serviços de US2 (email/account/apikey/usage).
- US3/US4/US5 iniciam quando suas dependências (US1/US2, T017) estiverem prontas.

---

## Notes

- `[P]` = arquivos diferentes, sem dependências.
- Verificar que os testes falham antes de implementar (Princípio III).
- Commit após cada tarefa ou grupo lógico.
- Dados oficiais são imutáveis em runtime; derivados de IA sempre marcados como não-oficiais.
- Nenhuma config insegura pode subir em produção (fail-fast) — regressão coberta por T018.
- Valores de cota/limiar/limites de IA e política de senha estão fixados em spec.md e nos contracts/.
