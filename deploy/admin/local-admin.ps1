<#
  deploy/admin/local-admin.ps1 - Painel /admin LOCAL contra o banco de PRODUCAO.

  Sobe, na sua maquina, o app com o painel /admin habilitado, conectado ao Cloud SQL
  de producao por um tunel autenticado (cloud-sql-proxy + suas credenciais IAM). Nada
  e exposto na internet: o painel roda so em 127.0.0.1. O admin_service e somente-leitura.

  Uso:
    ./deploy/admin/local-admin.ps1 start      # sobe proxy + app e abre o navegador
    ./deploy/admin/local-admin.ps1 stop       # derruba app + proxy
    ./deploy/admin/local-admin.ps1 status     # mostra o que esta no ar
    ./deploy/admin/local-admin.ps1 restart

  Parametros (opcionais):
    -AdminPassword <senha>   Senha do painel (dev). Default: "bncc-admin-local".
    -Port 8000               Porta do app.       -ProxyPort 5433   Porta do proxy.

  Pre-requisitos: gcloud autenticado como dono do projeto (fabio@expertia.dev.br) com
  ADC presente (gcloud auth application-default login), e o venv do projeto criado.
  Se o gcloud pedir reauthentication, rode 'gcloud auth login' uma vez no seu terminal.
  Alternativa: exporte $env:BNCC_ADMIN_DB_PASSWORD antes de 'start' para pular o gcloud.
#>
[CmdletBinding()]
param(
  [Parameter(Position = 0)]
  [ValidateSet("start", "stop", "status", "restart")]
  [string]$Action = "status",
  [string]$AdminPassword = "bncc-admin-local",  # pragma: allowlist secret (dev-only, local-only)
  [int]$Port      = 8000,
  [int]$ProxyPort = 5433,
  [string]$Project        = "api-bncc",
  [string]$ConnectionName = "api-bncc:southamerica-east1:bncc-pg",
  [string]$DbUser = "bncc_app",
  [string]$DbName = "bncc"
)

$ErrorActionPreference = "Stop"
$Here     = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $Here "..\..")
$BinDir   = Join-Path $Here "bin"
$Proxy    = Join-Path $BinDir "cloud-sql-proxy.exe"
$PidFile  = Join-Path $Here ".local-admin.pids"
$LogDir   = Join-Path $Here ".logs"
$VenvPy   = Join-Path $RepoRoot "venv\Scripts\python.exe"
$ProxyVersion = "v2.14.3"

function Info($m) { Write-Host "==> $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "!!  $m" -ForegroundColor Yellow }
function Ok($m)   { Write-Host "OK  $m" -ForegroundColor Green }

function Get-PortPid([int]$p) {
  $c = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
  if ($c) { return ($c.OwningProcess | Select-Object -Unique) }
  return $null
}

function Ensure-Proxy {
  if (Test-Path $Proxy) { return }
  Info "Baixando cloud-sql-proxy $ProxyVersion (uma vez)"
  New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
  $url = "https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/$ProxyVersion/cloud-sql-proxy.x64.exe"
  Invoke-WebRequest -Uri $url -OutFile $Proxy
  Ok "Proxy baixado em $Proxy"
}

function Do-Start {
  if (-not (Test-Path $VenvPy)) { throw "venv nao encontrado em $VenvPy - crie o ambiente do projeto primeiro." }
  if (Get-PortPid $Port) { Warn "Ja ha algo na porta $Port (app). Rode 'stop' antes ou use outra -Port."; return }
  Ensure-Proxy
  New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

  # Senha do banco: por padrao vem do Secret Manager (nunca fica em disco). Se a env
  # BNCC_ADMIN_DB_PASSWORD ja estiver setada, usa ela e pula o gcloud (util quando o
  # gcloud esta pedindo reauth non-interativo ou em automacao).
  if (-not [string]::IsNullOrWhiteSpace($env:BNCC_ADMIN_DB_PASSWORD)) {
    Info "Usando DB_PASSWORD de BNCC_ADMIN_DB_PASSWORD (fornecida pelo ambiente)"
    $dbPass = $env:BNCC_ADMIN_DB_PASSWORD
  } else {
    Info "Lendo DB_PASSWORD do Secret Manager ($Project)"
    $env:CLOUDSDK_BILLING_QUOTA_PROJECT = $Project
    $dbPass = (gcloud secrets versions access latest --secret=DB_PASSWORD --project $Project 2>$null)
  }
  if ([string]::IsNullOrWhiteSpace($dbPass)) {
    throw "Falha ao obter DB_PASSWORD. Rode 'gcloud auth login' (reauth) ou exporte BNCC_ADMIN_DB_PASSWORD."
  }

  # 1) cloud-sql-proxy (usa ADC do gcloud)
  Info "Subindo cloud-sql-proxy em 127.0.0.1:$ProxyPort"
  $proxyProc = Start-Process -FilePath $Proxy `
    -ArgumentList @("--address", "127.0.0.1", "--port", "$ProxyPort", $ConnectionName) `
    -RedirectStandardOutput (Join-Path $LogDir "proxy.out.log") `
    -RedirectStandardError  (Join-Path $LogDir "proxy.err.log") `
    -WindowStyle Hidden -PassThru

  $ready = $false
  foreach ($i in 1..15) {
    Start-Sleep -Milliseconds 500
    if (Get-PortPid $ProxyPort) { $ready = $true; break }
  }
  if (-not $ready) { Warn "Proxy nao subiu - veja $LogDir\proxy.err.log"; Stop-Process -Id $proxyProc.Id -Force -ErrorAction SilentlyContinue; return }

  # 2) app (uvicorn) - painel ligado, senha do banco injetada pelo config via placeholder
  Info "Subindo o app (painel /admin) em http://127.0.0.1:$Port"
  $env:ENVIRONMENT    = "development"
  $env:ADMIN_MODE     = "1"
  $env:ADMIN_PASSWORD = $AdminPassword
  $env:DATABASE_URL   = "postgresql+asyncpg://${DbUser}:__DB_PASSWORD__@127.0.0.1:${ProxyPort}/${DbName}"
  $env:DB_PASSWORD    = $dbPass
  $env:LOG_LEVEL      = "INFO"
  $appProc = Start-Process -FilePath $VenvPy `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$Port") `
    -WorkingDirectory $RepoRoot `
    -RedirectStandardOutput (Join-Path $LogDir "app.out.log") `
    -RedirectStandardError  (Join-Path $LogDir "app.err.log") `
    -WindowStyle Hidden -PassThru

  "$($proxyProc.Id) $($appProc.Id)" | Set-Content -Path $PidFile -Encoding ascii

  $up = $false
  foreach ($i in 1..25) {
    Start-Sleep -Milliseconds 800
    try {
      $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/admin/login" -UseBasicParsing -TimeoutSec 3
      if ($r.StatusCode -eq 200) { $up = $true; break }
    } catch { }
  }
  if (-not $up) { Warn "App demorou a responder - veja $LogDir\app.err.log (talvez ainda carregando embeddings)." }

  Ok "Painel no ar: http://127.0.0.1:$Port/admin  (senha: $AdminPassword)"
  Start-Process "http://127.0.0.1:$Port/admin/login"
}

function Do-Stop {
  $killed = @()
  if (Test-Path $PidFile) {
    foreach ($id in ((Get-Content $PidFile) -split "\s+")) {
      if ($id -and (Get-Process -Id $id -ErrorAction SilentlyContinue)) {
        Stop-Process -Id $id -Force -ErrorAction SilentlyContinue; $killed += $id
      }
    }
    Remove-Item $PidFile -ErrorAction SilentlyContinue
  }
  # fallback: mata por porta (caso o PID file esteja obsoleto)
  foreach ($p in @($Port, $ProxyPort)) {
    $pp = Get-PortPid $p
    if ($pp) { $pp | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue; $killed += $_ } }
  }
  if ($killed.Count) { Ok "Encerrados PIDs: $($killed -join ', ')" } else { Info "Nada rodando." }
}

function Do-Status {
  $appPid   = Get-PortPid $Port
  $proxyPid = Get-PortPid $ProxyPort
  Write-Host "App  (porta $Port):      " -NoNewline
  if ($appPid)   { Ok "no ar (PID $appPid) -> http://127.0.0.1:$Port/admin" } else { Warn "parado" }
  Write-Host "Proxy (porta $ProxyPort): " -NoNewline
  if ($proxyPid) { Ok "no ar (PID $proxyPid) -> $ConnectionName" } else { Warn "parado" }
}

switch ($Action) {
  "start"   { Do-Start }
  "stop"    { Do-Stop }
  "restart" { Do-Stop; Start-Sleep -Seconds 1; Do-Start }
  "status"  { Do-Status }
}
