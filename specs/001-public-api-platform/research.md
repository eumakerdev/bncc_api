# Research: Plataforma Pública da BNCC API (Fase 0)

Decisões técnicas que resolvem os pontos abertos da Technical Context. Cada item segue o formato
**Decisão / Racional / Alternativas consideradas**. Nenhum marcador NEEDS CLARIFICATION permanece.

---

## 1. Arquitetura das superfícies visuais (landing + portal + docs)

**Decisão**: Um único serviço FastAPI serve tudo. Landing page e portal do desenvolvedor são
**server-rendered com Jinja2 + Tailwind CSS**; a documentação interativa é gerada automaticamente do
contrato OpenAPI (Swagger UI nativo do FastAPI + uma página "docs" estilizada que embute o mesmo
spec). Tailwind é pré-compilado para um CSS estático (sem CDN em runtime).

**Racional**:
- SEO (FR-020/FR-021, SC-008 ≥ 90) exige HTML renderizado no servidor com meta tags, Open Graph,
  JSON-LD e sitemap — SSR entrega isso com TTFB baixo e sem hidratação.
- Mantém a **stack canônica** (Constituição: Python/FastAPI) e o Princípio VII (simplicidade): um só
  runtime, um só artefato de deploy, um só pipeline de testes.
- A documentação "gerada automaticamente do contrato" (FR-013/014/015) é uma propriedade nativa do
  FastAPI: todo endpoint tipado com Pydantic aparece no `/api/v1/openapi.json` → Swagger UI (com
  "testar" autenticado por API key) sem edição manual.

**Alternativas consideradas**:
- **SPA separada (Next.js/React)**: melhor DX de front, mas adiciona runtime Node, build e deploy
  próprios — viola stack canônica e YAGNI; SSR/SSG do Next resolveria SEO mas a um custo operacional
  injustificado para v1. Rejeitada.
- **Landing 100% estática (HTML gerado por script)**: bom SEO, mas o portal precisa de sessão/estado
  (login, exibir keys/uso), então já teríamos servidor — unificar em SSR é mais simples que manter
  dois mundos. Rejeitada.

---

## 2. Persistência de contas, API keys e uso

**Decisão**: **SQLAlchemy 2.0 (async) + Alembic**, com **SQLite** em dev e caminho migrável a
**PostgreSQL** em produção sem mudar código de domínio. Tabelas: `developer_accounts`, `api_keys`,
`usage_records`, `email_verification_tokens`.

**Racional**:
- Credenciais e métricas exigem transações, unicidade (e-mail, prefixo de key) e consultas agregadas
  de uso — impossível de fazer com segurança sobre JSON/ChromaDB.
- SQLAlchemy async integra com o FastAPI async; Alembic dá migrações reproduzíveis (Constituição:
  migrações de dados reproduzíveis).
- SQLite mantém v1 sem infra externa; o mesmo ORM sobe para Postgres trocando a URL de conexão.

**Alternativas consideradas**:
- **SQLModel**: ergonômico (Pydantic+SQLAlchemy), mas seu suporte a Pydantic v2/async é menos maduro e
  o `mypy` é mais frágil; preferimos SQLAlchemy 2.0 tipado. Rejeitada para v1.
- **Guardar em JSON**: sem integridade/transação; inseguro para credenciais. Rejeitada.
- **Postgres já em dev**: overhead de infra local desnecessário; SQLite cobre o caso. Adiada para prod.

---

## 3. Autenticação: portal e API

**Decisão**:
- **Portal**: e-mail + senha. Senha com **Argon2** (`argon2-cffi` via passlib). Sessão via **JWT**
  assinado com `SECRET_KEY` (expiração de `ACCESS_TOKEN_EXPIRE_MINUTES`). Verificação de e-mail
  obrigatória (token de uso único, com expiração) antes de liberar geração de keys (FR-007).
- **API**: **API keys** apresentadas como `Authorization: Bearer <key>`. Guardadas **hasheadas**
  (SHA-256) no banco; um **prefixo** curto não sensível é armazenado em claro para lookup e exibição
  ("bncc_live_ab12…"). A key completa só é exibida uma vez, na criação.

**Racional**:
- Argon2 é o padrão recomendado atual para hashing de senha; JWT evita estado de sessão no servidor.
- Hashear a key e indexar por prefixo permite autenticação O(1) sem guardar o segredo em claro
  (Constituição V: segredos protegidos, sem vazamento).

**Alternativas consideradas**:
- **OAuth2/SSO corporativo**: fora de escopo do v1 (Assumptions). Rejeitada.
- **bcrypt**: aceitável, mas Argon2 é preferível para senhas novas. bcrypt fica como fallback.
- **Keys em claro**: risco inaceitável se o banco vazar. Rejeitada.

---

## 4. Rate limiting com cota dupla

**Decisão**: Dois limitadores independentes por API key:
- **Determinístico**: 60 req/min (janela deslizante) com pequeno burst (FR-010).
- **IA (busca semântica)**: ~20 req/min **+ teto diário**, medido à parte (FR-010a).

Implementação v1: contadores **in-process** (janela deslizante) espelhados em `usage_records` no
SQLite para métricas e teto diário durável. Respostas `429` incluem `Retry-After` e quando o limite
reseta. Instância única em v1 torna o estado in-process suficiente; Redis é o caminho de escala.

**Racional**:
- Cotas separadas contêm o custo de LLM sem penalizar os endpoints determinísticos (Princípio VII).
- Durabilidade do teto diário via SQLite evita reset indevido em restart; janela por minuto in-process
  é barata e rápida (p95 < 300 ms).

**Alternativas consideradas**:
- **Redis (slowapi/redis)**: necessário só com múltiplas instâncias; adia-se para escala (YAGNI).
- **Somente in-memory**: perderia o teto diário em restart. Rejeitada isoladamente.

---

## 5. Verificação de e-mail / envio

**Decisão**: Serviço de e-mail assíncrono via **SMTP** (`aiosmtplib`), com **backend de console** em
dev (loga o link de verificação) e SMTP real em produção configurado por ambiente. Token de
verificação de uso único, com expiração, armazenado hasheado.

**Racional**: desacopla o domínio do provedor; dev não depende de e-mail real; segredos SMTP vêm do
ambiente (Constituição V).

**Alternativas consideradas**: SDK de provedor específico (SendGrid/SES) — evita-se acoplamento a um
fornecedor no v1; SMTP é universal e configurável. Reavaliar em produção.

---

## 6. Extração exaustiva e determinística da BNCC

**Decisão**: Reescrever `scripts/extract_bncc_data.py` para **parsing real** dos PDFs oficiais com
**pdfplumber** (melhor extração de texto/estrutura que PyPDF2), com parsers determinísticos por etapa
guiados pelos padrões oficiais de código:
- **Ensino Fundamental**: `EF<ano(s)><COMP><NN>` (ex.: `EF05MA07`, `EF15LP01`, `EF67EF01`).
- **Ensino Médio**: `EM13<AREA><NNN>` (ex.: `EM13MAT101`), incluindo itinerários quando presentes.
- **Educação Infantil**: `EI<faixa><CAMPO><NN>` (ex.: `EI03EO01`) — campos de experiência e
  objetivos de aprendizagem; se não houver PDF de EI em `data/`, ingerir de fonte oficial estruturada
  equivalente (dependência declarada na spec).

Saída: **snapshot único versionado** `data/bncc_v1.json` com metadados (versão, data, checksum das
fontes). Um script `validate_bncc_coverage.py` valida completude (contagens por etapa/componente),
unicidade de códigos, formato de código por etapa e integridade referencial (habilidade→competências/
objetos). Discrepâncias com a fonte são **defeitos de correção**, registrados, não corrigidos
silenciosamente (Princípio IV).

**Racional**: determinismo + versionamento + validação satisfazem FR-002/FR-003 e SC-001/SC-002. O
snapshot estático imutável em runtime atende à decisão de versionamento de dados.

**Alternativas consideradas**:
- **PyPDF2** (atual): extração de texto pobre em layouts com colunas/tabelas. Substituído por
  pdfplumber. (PyPDF2 pode permanecer para checagens simples.)
- **Extração assistida por LLM**: não-determinística e sujeita a alucinação — inaceitável para a fonte
  de autoridade (Princípio IV). Rejeitada como fonte da verdade (pode auxiliar QA humano, offline).
- **Atualização em runtime**: fora de escopo; v1 é snapshot (FR-003). Rejeitada.

---

## 7. Modelo de dados da BNCC — completar a taxonomia oficial

**Decisão**: Estender `app/models/bncc.py` para cobrir a taxonomia completa citada nas *Key Entities*:
adicionar **Campo de Experiência** e objetivos de aprendizagem (Educação Infantil), **Unidade
Temática** e **Objeto de Conhecimento** como entidades navegáveis, e habilidades/competências do
**Ensino Médio** (áreas `EM13...`, itinerários). Relaxar/ajustar o validador de `codigo` para aceitar
os três formatos oficiais (EI/EF/EM). Expor relações navegáveis (FR-005) por links/IDs nas respostas.

**Racional**: a arquitetura de dados deve derivar da taxonomia oficial (Overview da spec) e cobrir as
três etapas (SC-001). O modelo atual cobre parcialmente EF/EM e ignora EI.

**Alternativas consideradas**: manter o modelo atual mínimo — insuficiente para 100% de cobertura
(SC-001). Rejeitada.

---

## 8. Correção do desalinhamento de segurança (Constituição — Princípio V)

**Decisão**: Em `app/core/config.py`:
- Remover o padrão inseguro de `SECRET_KEY`; torná-lo **obrigatório** (sem default). Em produção
  (`ENVIRONMENT=production`) a app **falha rápido** na inicialização se `SECRET_KEY` estiver ausente
  ou for um valor de placeholder conhecido.
- `ALLOWED_HOSTS` **restrito por configuração** em produção (rejeitar `*`); default permissivo só é
  tolerado fora de produção.
- Validação de configuração no startup (Pydantic validators) que impede subir com config insegura
  (FR-023/SC-010). Handlers de erro globais que não vazam stack trace/paths (FR-024).

**Racional**: endereça diretamente o desalinhamento identificado e os requisitos FR-023/FR-024 e as
métricas SC-010.

**Alternativas consideradas**: manter defaults com aviso em log — insuficiente; a Constituição exige
que a app **não suba** insegura em produção. Rejeitada.

---

## 9. Degradação graciosa da camada de IA

**Decisão**: A busca semântica isola dependências de LLM/embedding atrás do `ai_service`/
`vector_store` com **timeout e teto de tokens explícitos**. Falha de IA retorna erro acionável apenas
no endpoint de IA; **todos os endpoints determinísticos permanecem 100% funcionais** e a `readiness`
distingue "IA indisponível" de "serviço fora". Resultados abaixo do limiar de similaridade não são
apresentados como oficiais; ausência de correspondência confiável é sinalizada (FR-016..FR-019).

**Racional**: Princípio VII e SC-009 (0% de degradação determinística durante falha de IA).

**Alternativas consideradas**: acoplar busca determinística ao mesmo caminho da IA — arriscaria o
núcleo em falhas de LLM. Rejeitada.

---

## 10. Design system minimalista consistente

**Decisão**: Um conjunto único de tokens (tipografia, espaçamento, paleta neutra sóbria) em Tailwind,
compartilhado por landing, portal e docs (FR-022). Componentes mínimos, foco em legibilidade e
performance (sem JS pesado na landing para preservar Lighthouse).

**Racional**: consistência visual exigida (FR-022) e metas de performance/acessibilidade (SC-008).

**Alternativas consideradas**: biblioteca de componentes pesada — custo de performance/complexidade
desnecessário para superfícies minimalistas. Rejeitada.

---

## Resumo de novas dependências

| Dependência | Papel | Princípio atendido |
|-------------|-------|--------------------|
| SQLAlchemy 2.0 (async) + Alembic + aiosqlite | Contas/keys/uso + migrações | II, III |
| argon2-cffi (via passlib) | Hash de senha | V |
| PyJWT | Sessão do portal | V |
| aiosmtplib | Verificação de e-mail | V |
| Jinja2 + Tailwind (build estático) | Landing/portal/docs SSR | I, VI |
| pdfplumber | Extração determinística de PDF | IV |

Todas são **adições** compatíveis com a stack canônica; nenhuma substitui componente estrutural nem
exige emenda à Constituição.
