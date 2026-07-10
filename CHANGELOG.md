# Changelog

Todas as mudanças relevantes deste projeto são registradas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o
projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/). A
versão referida abaixo é a da aplicação (campo `version` do app FastAPI); o
contrato público da API permanece em `/api/v1` e **não** sofre quebra dentro da
versão maior (Princípio I da [Constituição](.specify/memory/constitution.md)).

## [Não lançado]

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
