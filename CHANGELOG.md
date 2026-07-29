# Changelog

Todas as mudanças relevantes deste projeto são registradas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o
projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/). A
versão referida abaixo é a da aplicação (campo `version` do app FastAPI); o
contrato público da API permanece em `/api/v1` e **não** sofre quebra dentro da
versão maior (Princípio I da [Constituição](.specify/memory/constitution.md)).

## [Não lançado]

### Alterado — emenda constitucional v1.1.0 (LangChain fora da stack canônica)

A stack canônica de RAG passa de `sentence-transformers/LangChain` para
`sentence-transformers` em uso direto. `langchain`/`langchain-community` nunca foram
importados em `app/`, `scripts/` ou `tests/` — eram dependência morta cujos pinos
legados (`langchain==0.1.0`) travavam `numpy<2` e `packaging<24` e quebravam a
resolução do pip nos PRs do Dependabot. **Nenhuma mudança de contrato público**
(Princípio I) e nenhuma mudança de comportamento em runtime.

- `.specify/memory/constitution.md`: 1.0.0 → **1.1.0** (MINOR — redefinição material de
  uma restrição operacional, sem remoção/redefinição de princípio ou governança).
- `requirements.txt`: `langchain`/`langchain-community` removidos; com o teto de
  `packaging` liberado, os pinos anti-backtracking `build==1.3.0`/`packaging==23.2`
  também saíram; `google-cloud-bigquery` 3.30.0 → 3.42.2.
- `.github/dependabot.yml`: ignores de langchain e do teto do bigquery removidos —
  `numpy` 2.x e `pandas` 3.x ficam livres para o Dependabot propor.

### Alterado — custo de operação (auditoria de 2026-07-28)

Auditoria do faturamento real (billing export → BigQuery, cruzado com o Cloud
Monitoring) apontou **~R$450/mês para servir ~100 requisições/dia** — R$0,15 por
requisição. **72% era uma instância ociosa do Cloud Run** (2 vCPU/4 GiB, CPU p99
medida em **1%**) mantida ligada 24/7 apenas para esconder um cold start de **70s**.
Nenhuma mudança no contrato público (Princípio I).

- **Camada de IA carregada sob demanda.** `torch`/`SentenceTransformer` deixaram de
  ser carregados no lifespan e sobem na primeira busca semântica
  (`vector_store.get_vector_service`, com lock contra carga concorrente). O boot da
  aplicação caiu de **~70s para ~1,5s** e o núcleo determinístico deixou de pagar
  ~1,2 GiB de memória pela IA que talvez nunca use — reforço direto do Princípio VII.
  O readiness passa a sondar o índice em disco em vez de carregar o modelo,
  **preservando os valores `available`/`unavailable` do contrato**.
- **Cloud Run redimensionado** para `--min-instances=0 --cpu=1 --memory=2Gi`
  (era `1`/`2`/`4Gi`), com `--timeout=300` para acomodar a carga do modelo na
  primeira busca de um container novo. Contrapartida assumida: a primeira
  requisição após ociosidade paga alguns segundos de cold start.
- **Landing com `Cache-Control` público** (`s-maxage=600, stale-while-revalidate=3600`,
  alinhado ao TTL do cache de transparência). Sem header explícito, o Firebase
  Hosting marcava a página como `private` e todo acesso atravessava até o Cloud Run;
  agora a CDN absorve o tráfego e visitantes/crawlers não veem o cold start.
- **Imagem de produção enxuta**: `torch` instalado do índice CPU-only do PyTorch (a
  wheel padrão do PyPI embute ~2,5 GB de runtime CUDA inútil sem GPU), ferramentas
  de teste/lint/docs e a stack de extração de PDF movidas para o novo
  **`requirements-dev.txt`** (nada em `app/` as importa), e o `chown -R` que
  duplicava a árvore inteira numa camada extra eliminado via `COPY --chown`.
- **Política de limpeza no Artifact Registry** (`deploy/artifact-cleanup-policy.json`,
  reaplicada a cada deploy): a tag da imagem é reusada, então cada deploy órfãnava
  vários GB sem nada para recolhê-los — o repositório havia chegado a 66,8 GB.
- **Cloud Build** volta à máquina padrão, elegível aos 120 min/dia gratuitos.
- **Backtracking do pip eliminado.** `chromadb` pede `build>=1.0.3`, mas `build>=1.4.0`
  exige `packaging>=24.0` enquanto `langchain-core` 0.1.x exigia `packaging<24.0` — o
  pip descia versão a versão de `build` **re-resolvendo a árvore inteira a cada
  tentativa** (~175s por iteração, medidos), vários minutos desperdiçados em todo build
  de imagem. A mitigação inicial foram os pinos `build==1.3.0`/`packaging==23.2`;
  com a remoção do LangChain (Constituição v1.1.0, abaixo) o conflito deixou de existir
  e os pinos foram retirados. Além do custo, o build passa a ser reprodutível
  (Princípio IV).
- **Pool de conexões dimensionado** (`pool_size=2, max_overflow=3`): os defaults do
  SQLAlchemy permitiam até 60 conexões contra um `db-f1-micro` que sustenta ~25.
  `pool_pre_ping`/`pool_recycle` passam a importar porque o serviço agora escala a
  zero e recicla instâncias com frequência.
- Regressão de custo em `tests/integration/test_lazy_ai_startup.py`: um subprocesso
  limpo garante que o startup não importa `torch`/`sentence_transformers`/`chromadb`.
  Sem esse teste a regressão seria silenciosa — nada quebra, só volta a custar caro.

### Segurança

- **Content-Security-Policy** adicionada a todas as respostas (Princípio V —
  defesa em profundidade). Emitida em modo **Report-Only por padrão** (não
  bloqueia nada; rollout sem risco para a referência Scalar e as páginas SSR);
  vira bloqueante com `CSP_ENFORCE=true` após validação em navegador. Sem impacto
  no contrato público (Princípio I).
- **Container roda como usuário não-root** (menor privilégio) e a imagem não leva
  mais as ferramentas de build (`gcc`/`g++`) para runtime — superfície de ataque
  reduzida. O gate de build do CI valida a imagem.
- **Varreduras de segurança no CI**: análise estática **CodeQL** (SAST) e
  `dependency-review` informativo em PRs. Scan de segredos permanece no gate local
  de pre-commit (`detect-secrets`); no CI a via recomendada é o Secret Scanning
  nativo do GitHub (repo público). Nenhuma altera o runtime.
- Postura de segurança e dívida rastreável consolidadas em
  `docs/seguranca-endurecimento.md`.

### Adicionado

- **Painel de BI de uso** no portal (`/portal/dashboard`): série diária dos
  últimos 30 dias (chamadas totais vs. bem-sucedidas) renderizada como gráfico de
  área **SSR determinístico** (SVG server-side, sem dependência de JS/CDN;
  degrada para tabela acessível — Princípio VII), mais KPIs de total de
  requisições e variação vs. período anterior, taxa de sucesso, uso de IA e keys
  ativas. Novo endpoint `GET /api/v1/usage/analytics` (`AccountAnalyticsResponse`).
- **Rastreio de desfecho das chamadas de API** para a taxa de sucesso: coluna
  aditiva `usage_records.error_count` (migração `0004`) e `UsageOutcomeMiddleware`
  que contabiliza requisições com desfecho de erro (>= 400) por key/bucket/dia,
  sem tocar o caminho quente das bem-sucedidas.
- **Gestão de senha** no portal e na API v1:
  - Trocar senha autenticado — `POST /api/v1/auth/change-password` e
    `/portal/account/password`.
  - Recuperação por e-mail (fluxo "esqueci a senha") com token de uso único —
    `POST /api/v1/auth/forgot-password`, `POST /api/v1/auth/reset-password` e as
    páginas `/portal/forgot-password` / `/portal/reset-password`. Nova tabela
    `password_reset_tokens` (migração `0005`); resposta anti-enumeração
    (Princípio V).

### Alterado

- Painel do portal redesenhado (shell com sidebar, cartões de KPI, tabela de
  keys refinada e pílulas de status), fiel ao design system por tokens (tema
  claro/escuro automático).
- Snapshots de OpenAPI (contrato e release `v1/1.3.0`) recongelados para incluir
  os novos caminhos retrocompatíveis sob `/api/v1` (sem quebra — Princípio I).

## [1.3.0] - 2026-07-07

### Adicionado

- **Documentação versionada** em dois eixos, mantendo o app FastAPI único (sem
  sub-apps montados — `app.dependency_overrides`, usado pela suíte de testes,
  não se propaga para sub-apps montados):
  - **Eixo 1 — coexistência de versões de contrato:** um registro de versões
    em `app/api/versions.py` passa a dirigir docs e OpenAPI por versão de forma
    genérica. Cada versão maior do contrato vive sob um prefixo de caminho
    estável (`/api/v1`, futuro `/api/v2`). OpenAPI ao vivo por versão em
    `GET /api/{slug}/openapi.json` (v1 pela rota nativa do FastAPI). Referência
    interativa (Scalar) por versão em `/docs/{slug}` (e `/docs` = a mais
    recente). Manifesto legível por máquina em `GET /api/versions`.
  - **Eixo 2 — histórico de releases:** `scripts/freeze_openapi.py` congela o
    OpenAPI enriquecido ao vivo, por release, em
    `docs/openapi/{slug}/{release}.json`, com manifesto
    `docs/openapi/{slug}/index.json`. Servido em
    `GET /api/{slug}/releases/{release}/openapi.json`. A referência Scalar ganha
    um seletor de versão para navegar releases históricos via
    `/docs/{slug}?release=X`.
- Novos endpoints e páginas: `GET /api/versions`,
  `GET /api/{slug}/openapi.json`,
  `GET /api/{slug}/releases/{release}/openapi.json` e as páginas `/docs/{slug}`.
- Referência de manutenção em `docs/versioning.md` (esquema de URLs, como o
  consumidor fixa uma versão, como o mantenedor corta um release e introduz uma
  nova versão maior).

### Alterado

- Construção do OpenAPI enriquecido movida de `app/main.py` para
  `app/api/openapi.py` (sem mudança no schema resultante).
- Teste de contrato passa a garantir que o release congelado mais recente casa
  com o schema ao vivo e não tem quebras (análogo a
  `tests/contract/test_openapi_contract.py`, Princípio III).
- `version` do app FastAPI: `1.2.0` → `1.3.0`.

> **Compatível com versões anteriores.** O contrato `/api/v1` permanece
> inalterado: `/api/v1/openapi.json` e `/docs` se comportam como antes. Nenhuma
> quebra de contrato — o Princípio I da Constituição é preservado; toda a
> mudança é aditiva (novas superfícies de documentação).

## [1.2.0] - 2026-07-07

### Adicionado

- **Otimização técnica de SEO** (somente superfícies web — nenhuma mudança no
  contrato `/api/v1`):
  - `og:image`/`twitter:image` agora em **PNG 1200×630** (redes sociais rejeitam
    SVG), com `og:image:width/height/type` declarados. O asset é gerado de forma
    reproduzível por `scripts/generate_og_image.py` (Pillow, ferramenta one-off
    fora do `requirements.txt`) a partir da identidade "leitor em camadas".
  - `GET /favicon.ico` no caminho padrão pedido por navegadores/crawlers
    (antes 404), multi-size 16/32/48.
  - `/docs` (Scalar): canonical **absoluto** via `SITE_URL` (antes relativo
    hardcoded), `og:url`, `og:image` e Twitter Card.
  - `noindex` em `/portal/login` (cobre também verify-email e erros de OAuth,
    que renderizam o mesmo template); login removido do sitemap. Signup
    permanece indexável (página de conversão).
  - `sitemap.xml` com `<priority>` por URL (lista curada `_SITEMAP_ENTRIES`);
    `robots.txt` com `Disallow: /api/`, `/portal/auth/` e `/redoc`.
  - `Cache-Control` na origem: `/static/*` e sitemap/robots (1h, via
    `app/web/staticfiles.py::CachedStaticFiles`), favicon (1 dia). HTML dinâmico
    segue sem cache público (histórico de envenenamento na CDN do Hosting).
  - Página **404 HTML** amigável (noindex) para rotas web quando o cliente
    aceita `text/html`; o handler global agora cobre também o `HTTPException`
    do Starlette, então 404 de rota inexistente em `/api/*` passa a responder
    no schema estável `{ detail, error_code }`.
  - JSON-LD da landing: `publisher.logo` corrigido para `logo-icon.svg`.

## [1.1.0] - 2026-07-06

### Adicionado

- **Onboarding do portal** (`/portal/onboarding`): após o login, o portal
  apresenta um formulário obrigatório de 5 perguntas (perfil, contexto de uso,
  caso de uso, etapas da BNCC de interesse e estágio do projeto), uma pergunta
  por vez, com barra de progresso e revisão de respostas anteriores. As
  respostas são slugs de um catálogo fechado (sem texto livre), validados no
  serviço de domínio (`app/services/onboarding_service.py`, Princípios II e V),
  e ficam na nova tabela `onboarding_profiles` (migração Alembic `0002`).
  O dashboard e a geração de keys pelo portal redirecionam para o onboarding
  enquanto ele não for concluído. Apenas superfície SSR do portal — **nenhuma
  mudança no contrato público `/api/v1`**.

## [1.0.1] - 2026-07-06

### Segurança

- Correção de **CVE-2024-47874** (Starlette): negação de serviço via
  `multipart/form-data` sem limite de tamanho. Resolvido ao subir `starlette`
  para `>=0.40.0` (fixado em `1.3.1`).
- Correção de **CVE-2026-48710** ("BadHost", Starlette): um header `Host`
  malformado (contendo `/`, `?` ou `#`) dessincronizava `request.url.path` do
  path realmente roteado, permitindo contornar decisões de segurança baseadas em
  path em middleware. Resolvido ao subir `starlette` para `>=1.0.1` — o
  framework agora rejeita (400) esses headers antes do roteamento. Incide
  diretamente sobre o controle nomeado no Princípio V da Constituição
  (`TrustedHostMiddleware` + `ALLOWED_HOSTS`).
- Adicionado teste de regressão do BadHost em
  `tests/integration/test_host_header_security.py` (Princípio III).

### Alterado

- Bump de dependências para viabilizar as correções acima, sem mudança no
  contrato público da API:
  - `fastapi` `0.104.1` → `0.139.0`
  - `starlette` (não fixado) → `1.3.1` (pin explícito)
  - `pydantic` `2.5.0` → `2.13.4` (exigido por `fastapi>=0.130`)
  - `pydantic-settings` `2.1.0` → `2.14.2`
- Middleware de headers de segurança reescrito como middleware ASGI puro
  (`@app.middleware("http")`/`BaseHTTPMiddleware` foram removidos no Starlette
  1.0). Comportamento observável idêntico: as mesmas respostas continuam saindo
  com `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` e, em
  produção, `Strict-Transport-Security`.
- Chamadas a `Jinja2Templates.TemplateResponse` (landing, docs, portal)
  migradas para a nova assinatura `(request, name, context)` exigida pelo
  Starlette 1.x. Sem mudança de comportamento das páginas.
