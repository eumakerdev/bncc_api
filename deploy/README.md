# Deploy — Google Cloud Run

Implanta a BNCC API em **Cloud Run** (serverless por container) com **Cloud SQL Postgres**
para o banco da plataforma (contas/API keys/uso) e a camada de **IA** (embeddings ChromaDB
assados na imagem + LLM opcional).

## Por que estas escolhas
- **Cloud Run**: bate direto com o `Dockerfile`, HTTPS automático, escala por demanda.
- **Cloud SQL Postgres**: o filesystem do Cloud Run é efêmero/read-only — SQLite se perderia a
  cada deploy/instância. O driver `asyncpg` conecta pelo socket em `/cloudsql/<conn>`.
- **Embeddings na imagem**: são derivados **determinísticos e não-oficiais** do snapshot
  versionado `data/bncc_v1.json` (Princípio IV/VII), então são gerados no `docker build` e ficam
  read-only — sem download de modelo no cold start.

## Pré-requisitos
- `gcloud` autenticado no projeto (`gcloud config get-value project` → `api-bncc`).
- Faturamento ativo no projeto.
- Python local (o script gera `SECRET_KEY`/`DB_PASSWORD` com `secrets.token_urlsafe`).
- (Opcional, para geração via LLM) uma `GOOGLE_API_KEY` (Gemini).

## Deploy

```powershell
# com IA completa (retrieval + geração via Gemini)
./deploy/cloudrun.ps1 -GoogleApiKey "AIza..."

# sem chave: o retrieval funciona e a resposta cai para um resumo determinístico
# das fontes oficiais (degradação graciosa — Princípio VII)
./deploy/cloudrun.ps1
```

O provedor é escolhido pela chave presente: com `GOOGLE_API_KEY` o script define
`LLM_MODEL=gemini-2.5-flash` (ajustável via `-LlmModel`) e `AI_MAX_OUTPUT_TOKENS=3000`
(o "thinking" do 2.5-flash consome tokens de saída; um teto baixo trunca a resposta).
Modelos como `gemini-1.5-flash`/`gemini-2.0-flash` foram descontinuados na API.

O script é **idempotente** — rode de novo para atualizar. Ele: habilita APIs, cria Artifact
Registry, provisiona Cloud SQL, gera/lê os secrets, faz o build da imagem, roda as migrações
Alembic (Cloud Run Job) e sobe o serviço; ao final fixa `ALLOWED_HOSTS` com a URL real.

## Segurança (Princípio V)
- `ENVIRONMENT=production` → a app **falha rápido** se `SECRET_KEY` for fraca ou `ALLOWED_HOSTS`
  contiver `*`. O script cuida de ambos.
- A senha do Postgres **não** vai em texto plano: `DATABASE_URL` carrega o placeholder
  `__DB_PASSWORD__`, e `app/core/config.py` substitui pelo secret `DB_PASSWORD` em runtime.
- Secrets ficam no **Secret Manager**; a service account de compute recebe apenas
  `secretmanager.secretAccessor`.

## Parâmetros úteis
`-Region` (default `southamerica-east1`), `-Tag`, `-SqlTier` (default `db-f1-micro`),
`-Service`, `-SqlInstance`. Veja o cabeçalho de `cloudrun.ps1`.

## E-mail de verificação (Brevo)
Sem credenciais SMTP o serviço sobe com `EMAIL_BACKEND=console` (o link de verificação só aparece
nos logs do Cloud Run). Para signup self-service **real**, usamos o **Brevo** (ex-Sendinblue):
free tier de 300 e-mails/dia, SMTP puro.

**Passo a passo (uma vez):**
1. Crie a conta no Brevo e, em **Senders, Domains & Dedicated IPs → Domains**, adicione
   `bncc.api.br`. O Brevo mostra os registros **SPF, DKIM e DMARC** — publique-os no DNS do
   domínio. Sem isso o e-mail cai em spam.
2. Em **SMTP & API → SMTP**, copie o **login** (algo como `8xxxxx@smtp-brevo.com`) e gere uma
   **SMTP key** (a senha).
3. Rode o deploy passando as duas credenciais — elas vão para o **Secret Manager**
   (`SMTP_USERNAME`/`SMTP_PASSWORD`), e o script liga `EMAIL_BACKEND=smtp` só no serviço:

   ```powershell
   ./deploy/cloudrun.ps1 -GoogleApiKey "AIza..." `
     -BrevoSmtpUser "8xxxxx@smtp-brevo.com" -BrevoSmtpKey "<sua-smtp-key>"
   ```

   Como as credenciais ficam em secrets, **re-execuções não precisam repassá-las** (o script
   detecta os secrets e mantém `smtp`). O remetente padrão é `no-reply@bncc.api.br`
   (ajuste com `-EmailFrom`); host/porta são `smtp-relay.brevo.com:587` (`-SmtpHost`/`-SmtpPort`).

## Domínio custom — `bncc.api.br` (via Firebase Hosting)

A região `southamerica-east1` **não** oferece o *domain mapping* nativo do Cloud Run, então o
domínio é servido pelo **Firebase Hosting**, que faz proxy de `/**` para o serviço Cloud Run
(SSL grátis e gerenciado, CDN, sem custo fixo de load balancer). A config já está versionada em
`firebase.json` (rewrite `**` → serviço `bncc-api` em `southamerica-east1`) e `.firebaserc`
(projeto `api-bncc`).

> **Importante (verificado em produção):** atrás do Firebase Hosting o container recebe o `Host`
> **interno do `.run.app`** — o Firebase **não** repassa o domínio público como `Host`. Duas
> consequências, ambas já tratadas pelo `cloudrun.ps1`:
> - **URL canônica:** não pode derivar do request (senão vaza a URL do Cloud Run). Por isso existe
>   `SITE_URL=https://bncc.api.br`, injetada nos templates (canonical/OG/sitemap/robots) e no
>   *server* do OpenAPI. É a peça que garante SEO correto.
> - **`ALLOWED_HOSTS`:** lista o domínio custom + `.web.app`/`.firebaseapp.com` (origens de **CORS**
>   dos navegadores) e a URL direta do `.run.app` (que é o `Host` real que o `TrustedHost` vê). O
>   `EMAIL_VERIFICATION_BASE_URL` também aponta para `https://bncc.api.br`.

**Passo a passo (uma vez):**

1. **Ativar o Firebase no projeto GCP** `api-bncc` (o GCP e o Firebase compartilham o projeto):
   ```powershell
   npm install -g firebase-tools     # requer Node.js
   firebase login
   firebase projects:addfirebase api-bncc   # idempotente; ou pelo console do Firebase
   ```
   > Rewrites do Hosting para Cloud Run exigem o **plano Blaze** (pay-as-you-go). O projeto já
   > tem faturamento ativo (Cloud SQL/Run), então é só confirmar o Blaze no Firebase — o Hosting
   > em si tem free tier generoso (10 GB de storage, 360 MB/dia de transferência).
2. **Publicar o Hosting** (na raiz do repo — usa `firebase.json` + `.firebaserc`):
   ```powershell
   firebase deploy --only hosting
   ```
   Isso já deixa o app no ar em `https://api-bncc.web.app` (proxy p/ Cloud Run) — teste antes de
   mexer no DNS.
3. **Conectar o domínio custom**: Console do Firebase → **Hosting → Add custom domain** →
   `bncc.api.br`. O Firebase exibe:
   - um registro **TXT** de verificação de propriedade;
   - dois registros **A** (IPs do Firebase Hosting) a publicar depois da verificação.
4. **DNS no Registro.br**: painel do domínio → **DNS → Editar Zona** → adicione o **TXT** de
   verificação; após o Firebase validar, adicione os dois **A** records fornecidos (apex ou
   subdomínio `bncc`, conforme o domínio). Propagação + emissão do SSL gerenciado pode levar até
   ~24h.
5. **Redeploy do Cloud Run** para fixar os hosts do domínio (o passo 8 já faz isso):
   ```powershell
   ./deploy/cloudrun.ps1 -SkipBuild   # -SkipBuild: só atualiza env, sem rebuild pesado
   ```
   Parâmetros `-CustomDomain` / `-FirebaseProject` permitem trocar o domínio/projeto.

**E-mail (Brevo) no mesmo DNS**: os registros **SPF, DKIM e DMARC** do Brevo (seção acima) também
são publicados na **mesma zona do Registro.br** — sem eles o e-mail de verificação cai em spam.

## Follow-ups conhecidos
- **Nova versão de dados**: como os embeddings são assados na imagem, regenerar o snapshot exige
  novo build (novo `-Tag`) e redeploy.

## Custo (ordem de grandeza)
Cloud SQL `db-f1-micro` roda continuamente (~US$ 8–10/mês). Cloud Run com `--min-instances=1`
(escolhido para evitar cold start pesado de ML) mantém 1 instância ativa e também gera custo
contínuo — baixe para `0` se puder tolerar cold start, ou suba o `min` conforme a carga.
E-mail via **Brevo** é gratuito no free tier (300/dia) — sem custo adicional nesta fase.

## Transparência de custos (seção pública da landing)
A landing tem uma seção **"Transparência de custos"** que mostra o custo real de infraestrutura
(mensal + acumulado, por serviço, em BRL) faturado pelo Google Cloud. O dado vem do **billing
export para BigQuery**; um Cloud Run Job (`scripts/ingest_costs.py`) agrega o export e popula a
tabela `cost_records`. **A landing lê apenas o banco — nunca o BigQuery** (determinismo/degradação
graciosa, Princípio VII): se não houver dados, a seção simplesmente não aparece.

Setup:
1. **Habilitar o export (manual, uma vez):** console GCP → *Faturamento → Exportação de
   faturamento → BigQuery* → escolher/criar um dataset (ex.: `billing_export`). O export leva
   ~24h para começar a popular. A tabela criada tem nome tipo
   `gcp_billing_export_v1_XXXXXX_XXXXXX_XXXXXX`.
2. **Provisionar Job + agendamento + IAM:** rode `deploy/cloudrun.ps1` passando
   `-BillingDataset <dataset> -BillingTable <tabela>` (opcional `-CostCron "0 6 * * *"`). O script
   concede à service account do Cloud Run `roles/bigquery.dataViewer` + `roles/bigquery.jobUser`
   (IAM mínima), cria o Cloud Run Job `bncc-api-cost-ingest`, o dispara uma vez e agenda a execução
   diária via Cloud Scheduler. Sem esses parâmetros o bloco é ignorado (deploy inalterado).
3. **Backfill/manual:** `python scripts/ingest_costs.py --since 2026-01` (ou `--dry-run` para só
   inspecionar). Config via `GCP_PROJECT`/`GCP_BILLING_DATASET`/`GCP_BILLING_TABLE`.

A conta de faturamento brasileira fatura em **BRL** (usado direto). Se por acaso o export vier em
outra moeda, defina `USD_BRL_RATE` para converter.
