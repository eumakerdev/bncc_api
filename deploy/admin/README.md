# Painel de administração (`/admin`)

Ferramentas e operação do painel interno de **business intelligence** da plataforma
(contas, API keys, uso). O painel é isolado do site público e **nunca** é exposto por
padrão. Este diretório contém:

- **`local-admin.ps1`** — sobe o painel na sua máquina, contra o banco de **produção**,
  por um túnel autenticado (uso do dia a dia).
- **`deploy-admin.ps1`** — provisiona um serviço remoto isolado atrás do **Google IAP**
  (só quando você precisar de acesso web; ver a seção final).

> ## Nota de segurança (projeto open-source)
> **Nenhum segredo real vive neste repositório.** As senhas/chaves de produção
> (`DB_PASSWORD`, `SECRET_KEY`, credenciais OAuth) ficam no **Google Secret Manager** e
> são lidas em tempo de execução. O único valor "sensível-aparente" versionado é a
> **senha padrão do painel em modo dev** (abaixo) — e ela **não concede nenhum acesso a
> produção** (ver "Por que isso é seguro").

---

## Uso local (recomendado)

Pré-requisitos: `gcloud` autenticado como dono do projeto (`fabio@expertia.dev.br`), ADC
presente (`gcloud auth application-default login`) e o `venv` do projeto criado.

Num terminal **PowerShell**, a partir da raiz do repositório:

```powershell
.\deploy\admin\local-admin.ps1 start      # sobe túnel + app e abre o navegador
.\deploy\admin\local-admin.ps1 status     # mostra o que está no ar
.\deploy\admin\local-admin.ps1 stop       # derruba tudo
.\deploy\admin\local-admin.ps1 restart
```

O `start` faz tudo sozinho: baixa o `cloud-sql-proxy` (uma vez, em `bin/`), lê o
`DB_PASSWORD` do Secret Manager, sobe o túnel para o Cloud SQL de produção e o app com
`ADMIN_MODE=1`, e abre `http://127.0.0.1:8000/admin`.

### Senhas

| O que | Onde se usa | Valor |
|---|---|---|
| **Senha do painel** (`-AdminPassword`) | login em `/admin/login` | **`bncc-admin-local`** (default dev) |
| **Senha do banco** (`DB_PASSWORD`) | conexão ao Cloud SQL | **sem default** — lida do Secret Manager automaticamente |

Trocar a senha do painel nesta sessão:

```powershell
.\deploy\admin\local-admin.ps1 start -AdminPassword "uma-senha-sua"
```

### Se o `gcloud` pedir *reauthentication*

Em execução não-interativa o `gcloud` pode falhar com
`cannot prompt during non-interactive execution`. Soluções:

1. Rode `gcloud auth login` uma vez e tente de novo; **ou**
2. Forneça a senha do banco pela env (pula o `gcloud`):
   ```powershell
   $env:BNCC_ADMIN_DB_PASSWORD = "<senha-do-banco>"
   .\deploy\admin\local-admin.ps1 start
   ```

---

## Por que isso é seguro (mesmo com a senha padrão pública)

A senha `bncc-admin-local` está no código, mas **não abre nada em produção**:

- **É dev-only.** `admin_password_enabled` é `False` quando `ENVIRONMENT=production`
  (ver `app/core/config.py`) — em produção **só** existe login por Google.
- **É local-only.** O painel só é montado com `ADMIN_MODE=1`, que o deploy público
  **não** define. Em `bncc.api.br/admin` (e na URL crua do Cloud Run) a rota é **404**.
- **Exige credenciais reais para servir dados.** O `local-admin.ps1` só lê o banco de
  produção através do `cloud-sql-proxy`, que autentica com **as suas credenciais Google
  (IAM/ADC)**. Quem clonar o repo e usar `bncc-admin-local` não alcança banco nenhum sem
  ter, antes, acesso IAM ao projeto `api-bncc`.

Em produção/remoto o acesso é **identidade por pessoa**: Google Sign-In restrito a
`ADMIN_ALLOWED_EMAILS`, com MFA da conta Google. A senha compartilhada é proibida lá
(fail-fast no boot).

---

## Acesso remoto (opcional) — serviço isolado atrás do Google IAP

Quando/se for preciso acesso web ao painel, `deploy-admin.ps1` provisiona um serviço
Cloud Run **separado** (`bncc-admin`) com ingress interno + Load Balancer HTTPS +
**Identity-Aware Proxy**, mapeado em `admin.bncc.api.br`. A autorização é feita via
`gcloud`/IAM (só e-mails com `roles/iap.httpsResourceAccessor` passam), e o app ainda
reaplica a allowlist `ADMIN_ALLOWED_EMAILS` — **dois portões independentes**.

```powershell
.\deploy\admin\deploy-admin.ps1 -AllowedEmails "voce@dominio.com,colega@dominio.com" `
  -IapClientId <oauth-client-id-do-IAP> -IapClientSecret <secret>
```

Passos manuais (só-Console) e detalhes: ver os comentários no topo de `deploy-admin.ps1`
e a seção "Painel de administração" em `deploy/README.md`.

---

## Arquivos de runtime (não versionados)

`bin/` (binário do proxy), `.logs/` e `.local-admin.pids` são gerados em execução e estão
no `.gitignore` deste diretório.
