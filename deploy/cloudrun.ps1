<#
.SYNOPSIS
  Provisiona e implanta a BNCC API no Google Cloud Run (Cloud SQL Postgres + IA).

.DESCRIPTION
  Idempotente: cada recurso e criado so se ainda nao existir. Executa, em ordem:
    1. Habilita APIs necessarias
    2. Artifact Registry (repositorio de imagens)
    3. Cloud SQL Postgres (instancia + banco + usuario)
    4. Secrets (SECRET_KEY, DB_PASSWORD; opcionais: GOOGLE_API_KEY, SMTP, OAuth)
    5. Build da imagem (gera embeddings dentro da imagem)
    6. Migracoes Alembic via Cloud Run Job
    7. Deploy do servico Cloud Run
    8. Atualiza ALLOWED_HOSTS/e-mail com o dominio custom + URLs de servico

  NOTAS de PowerShell 5.1:
   - Texto ASCII-only: scripts UTF-8 sem BOM quebram o parser.
   - gcloud escreve em stderr mesmo em sucesso; por isso NAO usamos
     ErrorActionPreference=Stop. O sucesso/falha e checado por $LASTEXITCODE
     (helpers Exists/Exec), nunca pela presenca de stderr.

  Pre-requisitos: gcloud autenticado no projeto correto e faturamento ativo.

.EXAMPLE
  ./deploy/cloudrun.ps1 -GoogleApiKey "AIza..."
#>
[CmdletBinding()]
param(
  [string]$Project     = "api-bncc",
  [string]$Region      = "southamerica-east1",
  [string]$Repo        = "bncc",
  [string]$Image       = "api",
  [string]$Tag         = "v1",
  [string]$Service     = "bncc-api",
  [string]$SqlInstance = "bncc-pg",
  [string]$SqlTier     = "db-f1-micro",
  [string]$SqlEdition  = "ENTERPRISE",   # ENTERPRISE aceita tiers shared-core (db-f1-micro)
  [string]$DbName      = "bncc",
  [string]$DbUser      = "bncc_app",
  [string]$GoogleApiKey = "",    # chave Gemini p/ geracao da busca semantica (opcional)
  [string]$LlmModel    = "gemini-2.5-flash",
  [int]$AiMaxOutputTokens = 3000, # teto alto: o thinking do 2.5-flash consome tokens
  [string]$BrevoSmtpUser = "",   # login SMTP do Brevo (ex.: 8xxxxx@smtp-brevo.com) - habilita e-mail real
  [string]$BrevoSmtpKey  = "",   # chave/senha SMTP do Brevo (a "SMTP key" do painel)
  [string]$EmailFrom     = "no-reply@bncc.api.br", # remetente (dominio precisa de SPF/DKIM no Brevo)
  [string]$SmtpHost      = "smtp-relay.brevo.com",
  [int]$SmtpPort         = 587,
  [string]$CustomDomain    = "bncc.api.br",  # dominio custom servido via Firebase Hosting -> Cloud Run
  [string]$FirebaseProject = "api-bncc",     # projeto Firebase do Hosting (dominios .web.app/.firebaseapp.com)
  [string]$GoogleOAuthClientId     = "",  # login social Google (opcional; id+secret juntos habilitam)
  [string]$GoogleOAuthClientSecret = "",
  [string]$GithubOAuthClientId     = "",  # login social GitHub (opcional; id+secret juntos habilitam)
  [string]$GithubOAuthClientSecret = "",
  [switch]$SkipBuild             # reaproveita a imagem ja publicada (nao rebuilda)
)

$ErrorActionPreference = "Continue"
function Info($m) { Write-Host "==> $m" -ForegroundColor Cyan }

# Existencia: roda o comando, descarta todos os fluxos, retorna $true se exit 0.
function Exists([scriptblock]$Cmd) {
  & $Cmd *> $null
  return ($LASTEXITCODE -eq 0)
}
# Acao: roda o comando e ABORTA se o exit code for != 0 (ignora stderr benigno).
function Exec([scriptblock]$Cmd) {
  & $Cmd
  if ($LASTEXITCODE -ne 0) { throw "Comando gcloud falhou (exit $LASTEXITCODE): $Cmd" }
}

$ImageUri = "$Region-docker.pkg.dev/$Project/$Repo/${Image}:$Tag"
$Csql     = "${Project}:${Region}:${SqlInstance}"

Info "Projeto=$Project  Regiao=$Region  Imagem=$ImageUri"
Exec { gcloud config set project $Project }

# 1) APIs -----------------------------------------------------------------------
Info "Habilitando APIs"
Exec { gcloud services enable run.googleapis.com sqladmin.googleapis.com `
  artifactregistry.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com }

# 2) Artifact Registry ----------------------------------------------------------
Info "Artifact Registry ($Repo)"
if (-not (Exists { gcloud artifacts repositories describe $Repo --location=$Region })) {
  Exec { gcloud artifacts repositories create $Repo --repository-format=docker `
    --location=$Region --description="BNCC API images" }
}

# 3) Cloud SQL Postgres ---------------------------------------------------------
Info "Cloud SQL Postgres ($SqlInstance) - pode levar alguns minutos na 1a vez"
if (-not (Exists { gcloud sql instances describe $SqlInstance })) {
  Exec { gcloud sql instances create $SqlInstance --database-version=POSTGRES_16 `
    --edition=$SqlEdition --tier=$SqlTier --region=$Region --storage-auto-increase }
}
if (-not (Exists { gcloud sql databases describe $DbName --instance=$SqlInstance })) {
  Exec { gcloud sql databases create $DbName --instance=$SqlInstance }
}

# 4) Secrets --------------------------------------------------------------------
# Escrevemos o valor via arquivo temporario com WriteAllText (SEM newline). Piping
# `$v | gcloud ... --data-file=-` anexaria um \n ao segredo, quebrando a auth do
# Postgres (senha != senha+\n).
function Set-SecretValue([string]$Name, [string]$Value, [switch]$AddVersion) {
  # $path como string simples: dentro do scriptblock, `$tmp.FullName` expandiria
  # $tmp e anexaria ".FullName" como literal (bug de interpolacao do PowerShell).
  $path = (New-TemporaryFile).FullName
  [System.IO.File]::WriteAllText($path, $Value)
  try {
    if ($AddVersion) {
      Exec { gcloud secrets versions add $Name --data-file=$path }
    } else {
      Exec { gcloud secrets create $Name --data-file=$path }
    }
  } finally { Remove-Item $path -Force }
}
function Get-Secret([string]$Name) {
  return (gcloud secrets versions access latest --secret=$Name)
}

# Sincroniza um provedor OAuth: se id+secret foram passados, grava/atualiza ambos no
# Secret Manager (id tambem via secret para o deploy ser idempotente em re-execucoes,
# igual ao SMTP). Retorna $true se o provedor esta configurado (por param ou secret ja
# existente). client_secret nunca vai em env plano (Principio V).
function Sync-OAuthProvider([string]$Prefix, [string]$Id, [string]$Secret) {
  $idName  = "${Prefix}_OAUTH_CLIENT_ID"
  $secName = "${Prefix}_OAUTH_CLIENT_SECRET"
  if ($Id -and $Secret) {
    if (Exists { gcloud secrets describe $idName })  { Set-SecretValue $idName $Id -AddVersion }      else { Set-SecretValue $idName $Id }
    if (Exists { gcloud secrets describe $secName }) { Set-SecretValue $secName $Secret -AddVersion } else { Set-SecretValue $secName $Secret }
    return $true
  }
  return ((Exists { gcloud secrets describe $idName }) -and (Exists { gcloud secrets describe $secName }))
}

# Escreve um arquivo YAML de env vars para --env-vars-file. Evita o inferno de
# aspas do PowerShell/gcloud: ALLOWED_HOSTS precisa chegar ao container como JSON
# (`["host"]`) porque o pydantic-settings faz json.loads em campos list[str].
function Write-EnvFile([System.Collections.IDictionary]$Vars) {
  $path = (New-TemporaryFile).FullName + ".yaml"
  $lines = foreach ($k in $Vars.Keys) {
    $v = ([string]$Vars[$k]) -replace "'", "''"   # escapa aspas simples do YAML
    "${k}: '$v'"
  }
  [System.IO.File]::WriteAllText($path, (($lines -join "`n") + "`n"))
  return $path
}

# SECRET_KEY (JWT/sessao) - gerado forte uma unica vez
if (-not (Exists { gcloud secrets describe SECRET_KEY })) {
  Info "Criando secret SECRET_KEY"
  $sk = python -c "import secrets;print(secrets.token_urlsafe(48))"
  Set-SecretValue "SECRET_KEY" $sk
}

# DB_PASSWORD - gerado url-safe uma unica vez
if (-not (Exists { gcloud secrets describe DB_PASSWORD })) {
  Info "Criando secret DB_PASSWORD"
  $dbPass = python -c "import secrets;print(secrets.token_urlsafe(32))"
  Set-SecretValue "DB_PASSWORD" $dbPass
} else {
  $dbPass = Get-Secret "DB_PASSWORD"
}

# Alinha a senha do usuario do Postgres com o secret (idempotente)
Info "Sincronizando usuario $DbUser do Postgres"
$userExists = (gcloud sql users list --instance=$SqlInstance --format="value(name)") -contains $DbUser
if ($userExists) {
  Exec { gcloud sql users set-password $DbUser --instance=$SqlInstance --password="$dbPass" }
} else {
  Exec { gcloud sql users create $DbUser --instance=$SqlInstance --password="$dbPass" }
}

# GOOGLE_API_KEY (Gemini) - opcional; sem ela a geracao degrada para um resumo
# deterministico das fontes oficiais (o retrieval por embeddings segue funcionando).
$useGemini = $false
if ($GoogleApiKey) {
  if (Exists { gcloud secrets describe GOOGLE_API_KEY }) {
    Set-SecretValue "GOOGLE_API_KEY" $GoogleApiKey -AddVersion
  } else {
    Set-SecretValue "GOOGLE_API_KEY" $GoogleApiKey
  }
  $useGemini = $true
} elseif (Exists { gcloud secrets describe GOOGLE_API_KEY }) {
  $useGemini = $true
}
if (-not $useGemini) {
  Write-Host "AVISO: sem GOOGLE_API_KEY - busca semantica usa resumo deterministico (sem Gemini)." -ForegroundColor Yellow
}

# SMTP/Brevo (e-mail de verificacao real) - opcional; sem ele o backend fica em
# `console` e o link de verificacao so aparece nos logs do Cloud Run. Login e chave
# ficam ambos no Secret Manager para o deploy ser idempotente (re-lidos nas proximas
# execucoes sem precisar repassar -BrevoSmtp*). Precisa domain com SPF/DKIM no Brevo.
$useSmtp = $false
if ($BrevoSmtpUser -and $BrevoSmtpKey) {
  if (Exists { gcloud secrets describe SMTP_USERNAME }) {
    Set-SecretValue "SMTP_USERNAME" $BrevoSmtpUser -AddVersion
  } else { Set-SecretValue "SMTP_USERNAME" $BrevoSmtpUser }
  if (Exists { gcloud secrets describe SMTP_PASSWORD }) {
    Set-SecretValue "SMTP_PASSWORD" $BrevoSmtpKey -AddVersion
  } else { Set-SecretValue "SMTP_PASSWORD" $BrevoSmtpKey }
  $useSmtp = $true
} elseif ((Exists { gcloud secrets describe SMTP_USERNAME }) -and (Exists { gcloud secrets describe SMTP_PASSWORD })) {
  $useSmtp = $true
}
if (-not $useSmtp) {
  Write-Host "AVISO: sem SMTP (Brevo) - EMAIL_BACKEND=console; link de verificacao so nos logs." -ForegroundColor Yellow
}

# OAuth social (Google/GitHub) - opcional; sem credenciais o login social fica
# desabilitado (a app degrada). O redirect_uri usa OAUTH_REDIRECT_BASE_URL (dominio custom).
$useGoogleOAuth = Sync-OAuthProvider "GOOGLE" $GoogleOAuthClientId $GoogleOAuthClientSecret
$useGithubOAuth = Sync-OAuthProvider "GITHUB" $GithubOAuthClientId $GithubOAuthClientSecret
if (-not ($useGoogleOAuth -or $useGithubOAuth)) {
  Write-Host "AVISO: sem OAuth (Google/GitHub) - login social desabilitado (degrada)." -ForegroundColor Yellow
}

# Permite ao Cloud Run/Job ler os secrets
$projNum = gcloud projects describe $Project --format='value(projectNumber)'
$sa = "$projNum-compute@developer.gserviceaccount.com"
$secretNames = @("SECRET_KEY", "DB_PASSWORD")
if ($useGemini) { $secretNames += "GOOGLE_API_KEY" }
if ($useSmtp) { $secretNames += @("SMTP_USERNAME", "SMTP_PASSWORD") }
if ($useGoogleOAuth) { $secretNames += @("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET") }
if ($useGithubOAuth) { $secretNames += @("GITHUB_OAUTH_CLIENT_ID", "GITHUB_OAUTH_CLIENT_SECRET") }
foreach ($s in $secretNames) {
  Exec { gcloud secrets add-iam-policy-binding $s `
    --member="serviceAccount:$sa" --role="roles/secretmanager.secretAccessor" }
}

# DATABASE_URL com placeholder de senha (a app injeta DB_PASSWORD do secret)
$DatabaseUrl = "postgresql+asyncpg://${DbUser}:__DB_PASSWORD__@/${DbName}?host=/cloudsql/$Csql"

# 5) Build da imagem (gera embeddings dentro da imagem) -------------------------
if ($SkipBuild) {
  Info "SkipBuild: reaproveitando a imagem ja publicada ($ImageUri)"
} else {
  Info "Build da imagem (inclui geracao de embeddings - passo pesado de ML)"
  Exec { gcloud builds submit --config cloudbuild.yaml `
    --substitutions="_REGION=$Region,_REPO=$Repo,_IMAGE=$Image,_TAG=$Tag" }
}

# Env vars comuns (via arquivo YAML). ALLOWED_HOSTS vai como JSON array.
$envBase = [ordered]@{
  ENVIRONMENT    = "production"
  DATABASE_URL   = $DatabaseUrl
  BNCC_DATA_PATH = "/app/data/bncc_v1.json"
  CHROMADB_PATH  = "/app/data/chromadb"
  EMAIL_BACKEND  = "console"
  ALLOWED_HOSTS  = '["https://placeholder.invalid"]'
  SITE_URL       = "https://$CustomDomain"   # URL canonica p/ SEO/e-mail (dominio primario)
  OAUTH_REDIRECT_BASE_URL = "https://$CustomDomain"  # base do redirect_uri do callback OAuth
}
if ($useGemini) {
  $envBase["LLM_MODEL"] = $LlmModel
  $envBase["AI_MAX_OUTPUT_TOKENS"] = "$AiMaxOutputTokens"
}

# Mapeamento nome-do-env=nome-do-secret:versao (referencias, nao valores).
$commonSecrets = "SECRET_KEY=SECRET_KEY:latest,DB_PASSWORD=DB_PASSWORD:latest"  # pragma: allowlist secret
if ($useGemini) { $commonSecrets += ",GOOGLE_API_KEY=GOOGLE_API_KEY:latest" }

# 6) Migracoes Alembic via Cloud Run Job ----------------------------------------
Info "Migracoes Alembic (Cloud Run Job)"
$jobName = "$Service-migrate"
$jobVerb = if (Exists { gcloud run jobs describe $jobName --region=$Region }) { "update" } else { "create" }
$envFileJob = Write-EnvFile $envBase
Exec { gcloud run jobs $jobVerb $jobName `
  --image=$ImageUri --region=$Region `
  --set-cloudsql-instances=$Csql `
  --env-vars-file=$envFileJob `
  --set-secrets="$commonSecrets" `
  --command="alembic" --args="upgrade,head" }
Exec { gcloud run jobs execute $jobName --region=$Region --wait }
Remove-Item $envFileJob -Force

# 7) Deploy do servico ----------------------------------------------------------
# So o servico envia e-mail (o job de migracao segue em console). Se ha SMTP,
# ligamos o backend e injetamos host/porta/TLS/remetente por env; login e senha
# chegam por referencia de secret (Principio V - segredo nunca em env plano).
$svcSecrets = $commonSecrets
if ($useSmtp) {
  $envBase["EMAIL_BACKEND"] = "smtp"
  $envBase["EMAIL_FROM"]    = $EmailFrom
  $envBase["SMTP_HOST"]     = $SmtpHost
  $envBase["SMTP_PORT"]     = "$SmtpPort"
  $envBase["SMTP_USE_TLS"]  = "true"
  $svcSecrets += ",SMTP_USERNAME=SMTP_USERNAME:latest,SMTP_PASSWORD=SMTP_PASSWORD:latest"  # pragma: allowlist secret
}
# OAuth: id+secret chegam por referencia de secret (so no servico; o job nao faz login).
if ($useGoogleOAuth) { $svcSecrets += ",GOOGLE_OAUTH_CLIENT_ID=GOOGLE_OAUTH_CLIENT_ID:latest,GOOGLE_OAUTH_CLIENT_SECRET=GOOGLE_OAUTH_CLIENT_SECRET:latest" }  # pragma: allowlist secret
if ($useGithubOAuth) { $svcSecrets += ",GITHUB_OAUTH_CLIENT_ID=GITHUB_OAUTH_CLIENT_ID:latest,GITHUB_OAUTH_CLIENT_SECRET=GITHUB_OAUTH_CLIENT_SECRET:latest" }  # pragma: allowlist secret
Info "Deploy do servico Cloud Run ($Service)"
$envFileSvc = Write-EnvFile $envBase
Exec { gcloud run deploy $Service `
  --image=$ImageUri --region=$Region --platform=managed --allow-unauthenticated `
  --add-cloudsql-instances=$Csql `
  --memory=4Gi --cpu=2 --min-instances=1 --max-instances=4 --timeout=120 `
  --env-vars-file=$envFileSvc `
  --set-secrets="$svcSecrets" }
Remove-Item $envFileSvc -Force

# 8) Fixa ALLOWED_HOSTS/e-mail com o dominio custom + URLs de servico ------------
# Atras do Firebase Hosting o container recebe o Host INTERNO do .run.app (o Firebase
# nao repassa o dominio publico como Host) - por isso `SITE_URL` (passo acima) fixa a
# URL canonica de forma deterministica, sem depender de header. Aqui ALLOWED_HOSTS
# lista as origens publicas (CORS: dominio custom + .web.app/.firebaseapp.com) e a
# URL direta do Cloud Run (TrustedHost do acesso direto/health).
$Url = gcloud run services describe $Service --region=$Region --format="value(status.url)"
Info "URL do servico: $Url"
# Reutiliza $envBase (ja nao e mais necessario). Evitamos .Clone() porque
# OrderedDictionary nao implementa ICloneable.
$origins = @(
  "https://$CustomDomain",
  "https://$FirebaseProject.web.app",
  "https://$FirebaseProject.firebaseapp.com",
  $Url
)
$envBase["ALLOWED_HOSTS"] = '["' + ($origins -join '","') + '"]'
$envBase["EMAIL_VERIFICATION_BASE_URL"] = "https://$CustomDomain/portal/verify-email"
$envFileProd = Write-EnvFile $envBase
Exec { gcloud run services update $Service --region=$Region --env-vars-file=$envFileProd }
Remove-Item $envFileProd -Force

Info "Concluido. Dominio: https://$CustomDomain (via Firebase Hosting)  |  URL Run: $Url"
Info "Docs: https://$CustomDomain/docs  |  Landing: https://$CustomDomain/  |  Portal: https://$CustomDomain/portal"
