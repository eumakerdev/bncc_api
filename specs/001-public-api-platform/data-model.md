# Data Model: Plataforma Pública da BNCC API (Fase 1)

Dois domínios: (A) **Dados oficiais da BNCC** — snapshot estático versionado, somente leitura em
runtime; (B) **Plataforma** — contas, keys e uso, persistidos em banco relacional. Campos derivados
(embeddings/resumos) vivem no ChromaDB e são sempre marcados como não-oficiais.

Convenções: 🔒 = imutável em runtime (snapshot); 🗄️ = tabela relacional (SQLAlchemy); ✳️ = derivado/
não-oficial.

---

## A. Domínio BNCC (🔒 snapshot `data/bncc_v1.json`)

Deriva da taxonomia oficial. Modelado em `app/models/bncc.py` (Pydantic v2). Relações navegáveis por
código/ID (FR-005).

### Etapa de Ensino (enum)
`educacao_infantil` | `ensino_fundamental` | `ensino_medio`. Raiz da organização curricular.

### Área de Conhecimento (enum)
`linguagens` | `matematica` | `ciencias_natureza` | `ciencias_humanas` | `ensino_religioso`.

### Componente Curricular (enum)
`lingua_portuguesa` | `arte` | `educacao_fisica` | `lingua_inglesa` | `matematica` | `ciencias` |
`geografia` | `historia` | `ensino_religioso`. (Ensino Médio organiza por área; ver Habilidade.)

### Campo de Experiência (Educação Infantil) — **novo**
- `codigo` (ex.: `EO`, `CG`, `TS`, `EF`, `ET`), `nome` (ex.: "O eu, o outro e o nós")
- `objetivos_aprendizagem`: lista de objetivos (código `EI##<campo>##` + descrição)
- **Regra**: presente somente para `etapa = educacao_infantil`.

### Unidade Temática — **novo**
- `nome`, `componente` (FK enum), `etapa`
- Relação: agrupa **Objetos de Conhecimento** (Ensino Fundamental).

### Objeto de Conhecimento — **novo (entidade navegável)**
- `nome`, `unidade_tematica` (opcional), `componente`, `etapa`
- Relação: associado a **Habilidades** (N:N).

### Competência Geral
- `numero` (1–10), `titulo`, `descricao`. Transversal a todas as etapas.
- **Validação**: `1 ≤ numero ≤ 10`; exatamente 10 registros (SC-001).

### Competência Específica
- `codigo`, `numero`, `area_conhecimento`, `componente` (opcional), `etapa`, `descricao`
- **Regra**: referenciável por habilidades; cobre EI/EF/EM.

### Habilidade (entidade central)
- `codigo` (oficial), `descricao`, `etapa`, `anos` (lista), `area_conhecimento`, `componente`
- `competencias_gerais` (lista de 1–10), `competencias_especificas` (lista de códigos)
- `objetos_conhecimento` (lista), `campo_experiencia` (opcional, EI), `itinerario` (opcional, EM) ✳️? não — oficial quando presente
- **Validação de código** (aceitar os três formatos oficiais — FR corrige o validador atual):
  - EI: `^EI\d{2}[A-Z]{2}\d{2}$` (ex.: `EI03EO01`)
  - EF: `^EF\d{2}[A-Z]{2}\d{2}$` (ex.: `EF05MA07`, `EF15LP01`, `EF67EF01`)
  - EM: `^EM13[A-Z]{3}\d{3}$` (ex.: `EM13MAT101`)
- **Relações navegáveis**: habilidade → competências (gerais/específicas) → área/componente; e
  componente → unidade temática → objeto de conhecimento → habilidade (FR-005).

### Metadados do Snapshot — **novo**
- `versao` (ex.: `v1`), `data_publicacao`, `checksum_fontes`, `contagens` (por etapa/componente).
- Exposto por `/api/v1/sistema` (versão de dados) para rastreabilidade (FR-025 versionamento).

**Regras de integridade do snapshot** (validadas por `validate_bncc_coverage.py`, Princípio IV):
1. Todo `codigo` único e no formato da sua etapa.
2. Toda referência de `competencias_especificas`/`objetos_conhecimento` resolve para entidade
   existente.
3. Cobertura das **três** etapas > 0 e coerente com contagens oficiais (SC-001).
4. Campo derivado (embedding/resumo) nunca presente no snapshot oficial (só no ChromaDB, marcado ✳️).

---

## B. Domínio Plataforma (🗄️ SQLAlchemy async; migrações Alembic)

### DeveloperAccount 🗄️ (`developer_accounts`)
| Campo | Tipo | Regras |
|-------|------|--------|
| `id` | UUID/int PK | — |
| `email` | str | único, normalizado (lowercase), obrigatório |
| `password_hash` | str | Argon2; nunca exposto |
| `email_verified` | bool | default `false` |
| `created_at` / `updated_at` | datetime | — |

- **Estado**: `unverified` → (verifica e-mail) → `verified`. Geração de keys **exige** `verified`
  (FR-007).
- **Relações**: 1:N `ApiKey`; 1:N `EmailVerificationToken`.

### EmailVerificationToken 🗄️ (`email_verification_tokens`)
| Campo | Tipo | Regras |
|-------|------|--------|
| `id` | PK | — |
| `account_id` | FK | → DeveloperAccount |
| `token_hash` | str | hash do token de uso único |
| `expires_at` | datetime | expiração curta |
| `used_at` | datetime? | nulo até consumo (uso único) |

### ApiKey 🗄️ (`api_keys`)
| Campo | Tipo | Regras |
|-------|------|--------|
| `id` | PK | — |
| `account_id` | FK | → DeveloperAccount |
| `name` | str | rótulo dado pelo dev |
| `prefix` | str | não sensível, indexado, exibível (ex.: `bncc_live_ab12`) |
| `key_hash` | str | SHA-256 da key completa; segredo nunca em claro |
| `status` | enum | `active` \| `revoked` |
| `created_at` / `last_used_at` / `revoked_at` | datetime | — |

- **Estado**: `active` → (revogar) → `revoked`. Requisição com key `revoked`/inexistente → `401`
  imediato (FR-009, edge case).
- **Segredo completo** exibido **uma única vez** na criação; depois só `prefix`.
- **Relações**: 1:N `UsageRecord`.

### UsageRecord 🗄️ (`usage_records`)
| Campo | Tipo | Regras |
|-------|------|--------|
| `id` | PK | — |
| `api_key_id` | FK | → ApiKey |
| `bucket` | enum | `deterministic` \| `ai` (cotas separadas — FR-010/010a) |
| `window_start` | datetime | janela (min/dia) |
| `count` | int | requisições na janela |

- Fonte das **métricas por key** exibidas no painel (FR-011) e do **teto diário** de IA (FR-010a).
- Rate limiting por minuto usa contador in-process espelhado aqui; teto diário é durável no banco.

**Regras transversais de segurança/privacidade** (Princípios V/VI):
- Nunca logar `password_hash`, `key_hash`, tokens ou a key em claro.
- `email` é PII → fora de logs estruturados.
- Erros de auth retornam mensagem acionável sem revelar se o e-mail existe (anti-enumeração).

---

## Diagrama de relações (resumo)

```text
DeveloperAccount 1───N ApiKey 1───N UsageRecord
        │
        └───N EmailVerificationToken

Habilidade N───N Objeto de Conhecimento ──1 Unidade Temática ──1 Componente ──1 Área ──1 Etapa
   │  │
   │  └──N Competência Geral (1..10)
   └─────N Competência Específica
Habilidade(EI) ──1 Campo de Experiência ──N Objetivo de Aprendizagem
```

Contratos de request/response que expõem estas entidades: ver [contracts/](./contracts/).
