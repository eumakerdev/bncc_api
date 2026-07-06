# Changelog

Todas as mudanças relevantes deste projeto são registradas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o
projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/). A
versão referida abaixo é a da aplicação (campo `version` do app FastAPI); o
contrato público da API permanece em `/api/v1` e **não** sofre quebra dentro da
versão maior (Princípio I da [Constituição](.specify/memory/constitution.md)).

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
