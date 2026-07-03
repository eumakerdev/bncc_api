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

## Follow-ups conhecidos
- **E-mail**: sobe com `EMAIL_BACKEND=console` (link de verificação aparece nos logs do Cloud
  Run). Para signup self-service real, configure SMTP (`SMTP_HOST/USERNAME/PASSWORD` + secret) e
  troque para `EMAIL_BACKEND=smtp`.
- **Domínio custom**: mapeie no Cloud Run e ajuste `ALLOWED_HOSTS`/`EMAIL_VERIFICATION_BASE_URL`.
- **Nova versão de dados**: como os embeddings são assados na imagem, regenerar o snapshot exige
  novo build (novo `-Tag`) e redeploy.

## Custo (ordem de grandeza)
Cloud SQL `db-f1-micro` roda continuamente (~US$ 8–10/mês). Cloud Run com `--min-instances=1`
(escolhido para evitar cold start pesado de ML) mantém 1 instância ativa e também gera custo
contínuo — baixe para `0` se puder tolerar cold start, ou suba o `min` conforme a carga.
