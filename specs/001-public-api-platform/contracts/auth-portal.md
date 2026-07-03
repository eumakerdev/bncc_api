# Contract: Autenticação & Portal (P2)

Cadastro self-service com e-mail + senha e verificação de e-mail obrigatória (FR-007). Sessão do
portal via JWT. **Estes endpoints não usam API key** — usam sessão do portal.

## POST /api/v1/auth/signup
Cria conta de desenvolvedor (estado `unverified`) e dispara e-mail de verificação.
- **Body**: `{ email, password }` — `email` válido/normalizado; `password` com política mínima
  (**≥ 10 caracteres, ao menos letras e números**) validada por Pydantic.
- **201** → `{ account_id, email, email_verified: false }`. Envia link de verificação.
- **400** → e-mail inválido / senha fraca.
- **409** → e-mail já cadastrado — **mensagem neutra anti-enumeração** (não confirmar existência).
- **Aceite** (US2/AS1): após cadastro, conta existe mas **sem** acesso à geração de keys até verificar.

## POST /api/v1/auth/verify-email
Consome token de uso único enviado por e-mail.
- **Body/Query**: `{ token }`.
- **200** → `{ email_verified: true }` (habilita geração de keys).
- **400/410** → token inválido, expirado ou já usado.
- **Aceite** (US2/AS1): e-mail confirmado → painel libera criar/revogar keys.

## POST /api/v1/auth/login
- **Body**: `{ email, password }`.
- **200** → sessão (JWT) com expiração de `ACCESS_TOKEN_EXPIRE_MINUTES`.
- **401** → credenciais inválidas **ou** e-mail não verificado — mensagem acionável, sem revelar qual.
- **429** → tentativas excessivas (proteção anti-brute-force).

## POST /api/v1/auth/logout
- **200** → invalida a sessão do cliente.

## GET /api/v1/auth/me
- **200** → `{ account_id, email, email_verified }` da sessão atual. **401** sem sessão válida.

## Segurança (Princípio V; FR-023/FR-024)
- Senha hasheada com Argon2; nunca retornada nem logada.
- Tokens de verificação hasheados, uso único, com expiração.
- Respostas de erro sem stack trace/paths; mensagens anti-enumeração de e-mail.
- Reforço: com `ENVIRONMENT=production`, a app não sobe com `SECRET_KEY` padrão/ausente nem
  `ALLOWED_HOSTS=*` (validação de config no startup).

## Cobertura de teste de contrato
- signup → 201 + estado unverified; e-mail duplicado → 409 neutro.
- verify-email com token válido/expirado/reutilizado → 200/410.
- login antes de verificar → 401; depois de verificar → 200 com sessão.
- fluxo completo signup→verify→login habilita `/keys` (ver api-keys-usage).
