<#
  deploy/admin/deploy-admin.ps1 — Serviço de ADMIN isolado atrás do Google IAP.

  Fronteira 4 do plano de segurança (ver .claude/plans / specs). Sobe um serviço
  Cloud Run SEPARADO (`bncc-admin`) — a partir da MESMA imagem do serviço público —
  porém:
    - `--ingress=internal-and-cloud-load-balancing` + `--no-allow-unauthenticated`
      → o container NÃO é alcançável pela internet direto (só via o Load Balancer).
    - Atrás de um Load Balancer HTTPS externo com **Identity-Aware Proxy (IAP)**:
      o Google autentica o usuário ANTES de a requisição chegar ao app.
    - Autorização 100% via IAM/gcloud: só e-mails com
      `roles/iap.httpsResourceAccessor` passam pelo IAP. Defesa em profundidade:
      o app ainda exige `ADMIN_ALLOWED_EMAILS` (dois portões independentes).

  Pré-requisitos: a imagem `api:<Tag>` já publicada (rode antes o build do
  deploy/cloudrun.ps1, ou use a mesma tag), Cloud SQL `bncc-pg` no ar, secrets
  `SECRET_KEY`/`DB_PASSWORD`/`GOOGLE_OAUTH_*` no Secret Manager.

  IMPORTANTE — passos SÓ-CONSOLE (o gcloud não cobre): a **tela de consentimento
  OAuth (IAP brand)** e a criação do **OAuth client do IAP** são feitas uma única
  vez no Console (APIs & Services → OAuth consent screen; Security → IAP). O script
  aborta com instruções se elas não existirem. O apontamento DNS do subdomínio
  (Registro.br) também é manual.

  Uso:
    ./deploy/admin/deploy-admin.ps1 -AllowedEmails "voce@dominio.com,colega@dominio.com"
#>
param(
  [string]$Project      = "api-bncc",
  [string]$Region       = "southamerica-east1",
  [string]$Repo         = "bncc",
  [string]$Image        = "api",
  [string]$Tag          = "v1",
  [string]$Service      = "bncc-admin",
  [string]$SqlInstance  = "bncc-pg",
  [string]$DbName       = "bncc",
  [string]$DbUser       = "bncc_app",
  [string]$AdminDomain  = "admin.bncc.api.br",
  [Parameter(Mandatory = $true)]
  [string]$AllowedEmails,                 # "a@x.com,b@y.com" — allowlist do app E do IAP
  [string]$IapClientId     = "",          # do OAuth client do IAP (Console) — obrigatório p/ ligar o IAP
  [string]$IapClientSecret = "",
  [switch]$SkipService                    # reaproveita o serviço já implantado (só (re)configura LB/IAP)
)

$ErrorActionPreference = "Continue"
function Info($m) { Write-Host "==> $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "!!  $m" -ForegroundColor Yellow }
function Exists([scriptblock]$Cmd) { & $Cmd *> $null; return ($LASTEXITCODE -eq 0) }
function Exec([scriptblock]$Cmd) {
  & $Cmd
  if ($LASTEXITCODE -ne 0) { throw "Comando gcloud falhou (exit $LASTEXITCODE): $Cmd" }
}

$ImageUri = "$Region-docker.pkg.dev/$Project/$Repo/${Image}:$Tag"
$Csql     = "${Project}:${Region}:${SqlInstance}"
$AdminBase = "https://$AdminDomain"

Info "Projeto=$Project  Serviço=$Service  Domínio=$AdminDomain"
Exec { gcloud config set project $Project }
Exec { gcloud services enable run.googleapis.com compute.googleapis.com iap.googleapis.com }

# --------------------------------------------------------------------------- #
# 1) Serviço Cloud Run isolado (ingress restrito, sem acesso anônimo)
# --------------------------------------------------------------------------- #
if (-not $SkipService) {
  Info "Implantando serviço isolado $Service (ingress interno + LB, sem anônimo)"
  # DATABASE_URL com placeholder de senha (o DB_PASSWORD é injetado pelo config).
  $dbUrl = "postgresql+asyncpg://${DbUser}:__DB_PASSWORD__@/${DbName}?host=/cloudsql/$Csql"
  $adminEnv = @(
    "ENVIRONMENT=production",
    "ADMIN_MODE=1",
    "ADMIN_ALLOWED_EMAILS=$AllowedEmails",
    "DATABASE_URL=$dbUrl",
    "OAUTH_REDIRECT_BASE_URL=$AdminBase",
    "SITE_URL=$AdminBase",
    "ALLOWED_HOSTS=$AdminDomain"
  ) -join ","
  $adminSecrets = "SECRET_KEY=SECRET_KEY:latest,DB_PASSWORD=DB_PASSWORD:latest," +
    "GOOGLE_OAUTH_CLIENT_ID=GOOGLE_OAUTH_CLIENT_ID:latest," +
    "GOOGLE_OAUTH_CLIENT_SECRET=GOOGLE_OAUTH_CLIENT_SECRET:latest"

  Exec { gcloud run deploy $Service `
    --image=$ImageUri --region=$Region --platform=managed `
    --no-allow-unauthenticated `
    --ingress=internal-and-cloud-load-balancing `
    --add-cloudsql-instances=$Csql `
    --set-env-vars=$adminEnv `
    --set-secrets=$adminSecrets `
    --min-instances=0 --max-instances=2 }

  Warn "Lembre de adicionar '$AdminBase/admin/auth/google/callback' aos 'Authorized redirect URIs' do OAuth client Google (Console → APIs & Services → Credentials)."
}

# --------------------------------------------------------------------------- #
# 2) Load Balancer HTTPS externo → Serverless NEG do serviço
# --------------------------------------------------------------------------- #
$Neg     = "$Service-neg"
$Backend = "$Service-backend"
$UrlMap  = "$Service-urlmap"
$Cert    = "$Service-cert"
$Proxy   = "$Service-https-proxy"
$Rule    = "$Service-fr"
$Ip      = "$Service-ip"

Info "IP estático global"
if (-not (Exists { gcloud compute addresses describe $Ip --global })) {
  Exec { gcloud compute addresses create $Ip --global }
}
$IpAddr = (gcloud compute addresses describe $Ip --global --format="value(address)")

Info "Serverless NEG → $Service"
if (-not (Exists { gcloud compute network-endpoint-groups describe $Neg --region=$Region })) {
  Exec { gcloud compute network-endpoint-groups create $Neg `
    --region=$Region --network-endpoint-type=serverless --cloud-run-service=$Service }
}

Info "Backend service (com IAP)"
if (-not (Exists { gcloud compute backend-services describe $Backend --global })) {
  Exec { gcloud compute backend-services create $Backend --global `
    --load-balancing-scheme=EXTERNAL_MANAGED }
  Exec { gcloud compute backend-services add-backend $Backend --global `
    --network-endpoint-group=$Neg --network-endpoint-group-region=$Region }
}

# IAP no backend: exige o OAuth client do IAP (Console). Sem ele, para aqui.
if ($IapClientId -and $IapClientSecret) {
  Info "Habilitando IAP no backend $Backend"
  Exec { gcloud compute backend-services update $Backend --global `
    --iap=enabled,oauth2-client-id=$IapClientId,oauth2-client-secret=$IapClientSecret }
} else {
  Warn "IAP NÃO ligado: rode com -IapClientId/-IapClientSecret (crie o OAuth client em Console → Security → Identity-Aware Proxy). Depois re-execute com -SkipService."
}

Info "Certificado gerenciado + URL map + proxy + forwarding rule"
if (-not (Exists { gcloud compute ssl-certificates describe $Cert --global })) {
  Exec { gcloud compute ssl-certificates create $Cert --global --domains=$AdminDomain }
}
if (-not (Exists { gcloud compute url-maps describe $UrlMap --global })) {
  Exec { gcloud compute url-maps create $UrlMap --default-service=$Backend --global }
}
if (-not (Exists { gcloud compute target-https-proxies describe $Proxy --global })) {
  Exec { gcloud compute target-https-proxies create $Proxy `
    --url-map=$UrlMap --ssl-certificates=$Cert --global }
}
if (-not (Exists { gcloud compute forwarding-rules describe $Rule --global })) {
  Exec { gcloud compute forwarding-rules create $Rule --global `
    --target-https-proxy=$Proxy --address=$Ip --ports=443 }
}

# --------------------------------------------------------------------------- #
# 3) Autorização: quem pode passar pelo IAP (gcloud/IAM)
# --------------------------------------------------------------------------- #
if ($IapClientId -and $IapClientSecret) {
  Info "Concedendo acesso IAP à allowlist"
  foreach ($email in ($AllowedEmails -split ",")) {
    $e = $email.Trim()
    if ($e) {
      Exec { gcloud iap web add-iam-policy-binding `
        --resource-type=backend-services --service=$Backend `
        --member="user:$e" --role="roles/iap.httpsResourceAccessor" }
    }
  }
}

Write-Host ""
Info "Feito. Próximos passos MANUAIS:"
Write-Host "  1) DNS (Registro.br): crie um registro A  $AdminDomain -> $IpAddr" -ForegroundColor Gray
Write-Host "  2) Aguarde o certificado gerenciado ficar ACTIVE (pode levar ~15-60 min)." -ForegroundColor Gray
Write-Host "  3) Acesse $AdminBase → consentimento Google do IAP → painel." -ForegroundColor Gray
Write-Host "  Revogar acesso de alguém: gcloud iap web remove-iam-policy-binding ..." -ForegroundColor Gray
