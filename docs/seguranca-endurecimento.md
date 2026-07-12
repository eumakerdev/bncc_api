# Endurecimento de segurança — estado e dívida rastreável

Este documento registra a postura de segurança da BNCC API e a **dívida conhecida**
que, por risco de regressão, é rastreada aqui em vez de corrigida às cegas
(Constituição — Princípio V e seção *Governança*; Princípio VII: simplicidade e
mudança justificada). Cada item traz o risco, por que não foi resolvido agora e o
caminho seguro de resolução.

## Já implementado

| Controle | Onde |
| --- | --- |
| Fail-fast de config insegura em produção (`SECRET_KEY`, `ALLOWED_HOSTS=*`, OAuth pela metade) | `app/core/config.py::_enforce_production_security` |
| Senhas com Argon2; API keys hasheadas (SHA-256 sobre 256 bits); tokens de e-mail/reset hasheados | `app/core/security.py` |
| JWT com algoritmo fixo (`HS256`) — sem alg-confusion | `app/core/security.py::decode_access_token` |
| Headers de segurança: `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, HSTS (prod), **CSP (Report-Only por padrão)** | `app/main.py::SecurityHeadersMiddleware` |
| `TrustedHostMiddleware` + CORS restrito por config (não pode ser `*` em prod) | `app/main.py`, `app/core/config.py` |
| Erros sem stack trace / paths internos ao cliente | `app/core/errors.py` |
| Rate limiting por API key (determinístico + IA) e por IP (login/signup/verify/forgot/oauth/admin) | `app/core/deps.py` |
| Container roda como usuário **não-root**; ferramentas de build removidas da imagem | `Dockerfile` |
| CI: `detect-secrets` (mesmo rev do pre-commit), `dependency-review` em PR, `pip-audit`, CodeQL (SAST) | `.github/workflows/` |
| Dependências pinadas com CVEs anotadas; Dependabot ativo | `requirements.txt`, `.github/dependabot.yml` |

### Content-Security-Policy — rollout seguro

A CSP é emitida em modo **`Content-Security-Policy-Report-Only`** por padrão: ela
**não bloqueia nada**, apenas reporta violações ao console do navegador. Isso evita
qualquer risco de quebrar a referência interativa Scalar (`/docs`, bundle de
terceiros com scripts inline e `eval`) e as páginas SSR (landing/portal).

**Para ativar o modo bloqueante** (`CSP_ENFORCE=true`):

1. Suba a app com `CSP_ENFORCE=true` num ambiente de staging.
2. Abra num navegador real e exercite: `/`, `/guia`, `/docs` (expanda endpoints e
   use o "Test Request" do Scalar), `/portal` (login, signup, dashboard) e `/admin`.
3. Confirme que o console **não** acusa violação de CSP. Se acusar, ajuste
   `_CSP_POLICY` em `app/main.py` para a diretiva faltante e repita.
4. Só então defina `CSP_ENFORCE=true` em produção.

## Dívida rastreada (resolução requer coordenação — não mexer às cegas)

### 1. Stack de IA legada com CVEs (`chromadb 0.4.18`, `langchain 0.1.0`)

- **Risco:** CVEs conhecidas em transitivos; trava `numpy<2`. Por isso o `pip-audit`
  do CI é informativo (`continue-on-error`).
- **Por que não agora:** o LangChain 0.1 → 0.2/0.3 partiu o pacote-base
  (`langchain-core`/`langchain-community`); bump piecemeal quebra a resolução do pip
  (ver nota no `.github/dependabot.yml`). É migração coordenada, com risco real de
  regressão na busca semântica (Princípio VII: IA não pode derrubar o núcleo).
- **Caminho seguro:** migração dedicada em branch próprio, cobrindo a suíte da camada
  de IA + recalibração do threshold PT-BR; validar `scripts/generate_embeddings.py` e
  a busca ponta a ponta antes do merge. Só então tornar o `pip-audit` bloqueante para
  as dependências não-IA.

### 2. Rate limiting in-process (por instância, não global)

- **Risco:** no Cloud Run com N instâncias, o limite por minuto é aplicado por
  instância → teto efetivo ~N× o configurado. Só o teto **diário** (via DB) é global.
- **Por que não agora:** limitador global exige store compartilhado (Redis), nova
  dependência de infra e de deploy — mudança estrutural (Princípio VII: justificar
  complexidade). Trocar sem cuidado arrisca indisponibilidade do caminho quente.
- **Mitigação imediata (sem código):** fixar `--max-instances` baixo no serviço do
  Cloud Run mantém o teto efetivo previsível enquanto o Redis não chega.
- **Caminho seguro:** introduzir `SlidingWindowLimiter` com backend Redis atrás da
  mesma interface (`app/core/ratelimit.py`), com fallback in-process se o Redis cair
  (degradação graciosa), coberto por teste.

### 3. Confiança em `X-Forwarded-For` para rate limit por IP

- **Risco:** `_client_ip` usa o primeiro item do `X-Forwarded-For`. É seguro **hoje**
  porque no Cloud Run/Firebase o container só é alcançável pelo front-end do Google
  (que reescreve o header). Se o serviço for exposto diretamente, o IP vira spoofável.
- **Caminho seguro:** manter essa suposição de topologia documentada em
  `app/core/deps.py::_client_ip`; se um dia houver exposição direta, validar o número
  de proxies confiáveis em vez de confiar cegamente no primeiro item.

### 4. `mypy` com gate parcial

- **Estado:** bloqueante só nos módulos novos limpos; o legado roda `|| true`.
- **Caminho seguro (catraca):** a cada PR que tocar um módulo hoje fora do gate,
  adicioná-lo à lista bloqueante do `ci.yml`, fechando o cerco sem big-bang.

### 5. `last_used_at` de API key gravado sem commit explícito

- **Observação:** `app/core/deps.py::require_api_key` atribui `api_key.last_used_at`
  mas o commit depende do fluxo da request. É best-effort (métrica de auditoria, não
  controle de segurança).
- **Por que não agora:** alterar o commit no caminho quente de **toda** chamada
  autenticada arrisca contenção/regressão de performance. Requer teste dedicado.
- **Caminho seguro:** confirmar o comportamento com teste de integração antes de
  tornar a gravação explícita; medir impacto no p95 (Princípio VI).
