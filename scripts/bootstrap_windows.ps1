$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$LogDir = Join-Path $Root "logs"
$LogPath = Join-Path $LogDir "bootstrap-windows.log"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $Root

function Write-Step($Index, $Total, $Message) {
  $line = "[$Index/$Total] $Message"
  Write-Host $line -ForegroundColor Cyan
  Add-Content -Path $LogPath -Value "[$(Get-Date -Format o)] $line"
}

function Write-Fix($Title, $Reason, $Command) {
  Write-Host ""
  Write-Host "Khong the tu xu ly: $Title" -ForegroundColor Yellow
  Write-Host "Nguyen nhan: $Reason"
  Write-Host "Lenh goi y co the copy:"
  Write-Host "  $Command" -ForegroundColor Green
  Write-Host "Log: $LogPath"
  Add-Content -Path $LogPath -Value "FIX $Title :: $Reason :: $Command"
}

function Has-Command($Name) {
  return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Is-Admin {
  $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = New-Object Security.Principal.WindowsPrincipal($identity)
  return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Install-WithWinget($Id, $Name) {
  if (-not (Has-Command "winget")) {
    Write-Fix $Name "May chua co winget nen khong the cai tu dong." "Mo Microsoft Store va cai App Installer, sau do chay lai run.bat"
    return $false
  }
  if (-not (Is-Admin)) {
    Write-Host "Se thu cai $Name bang winget. Neu Windows hoi quyen admin, hay chap nhan." -ForegroundColor Yellow
  }
  winget install --id $Id -e --accept-package-agreements --accept-source-agreements
  return $true
}

$Total = 9
Write-Host "ForgeTrend V3 bootstrap Windows" -ForegroundColor White
Write-Host "Muc tieu: kiem tra dependency, cai nhung thu an toan khi co the, roi mo ForgeTrend." -ForegroundColor White
Write-Host "Khong tu dong publish app len store." -ForegroundColor White

Write-Step 1 $Total "Kiem tra Node.js"
if (-not (Has-Command "node")) {
  if (-not (Install-WithWinget "OpenJS.NodeJS.LTS" "Node.js LTS")) { exit 1 }
  Write-Fix "Can mo lai terminal" "PATH cua Node moi cai co the chua duoc nap vao phien nay." "Dong cua so nay, mo lai run.bat"
  exit 1
}

Write-Step 2 $Total "Kiem tra Git va internet"
if (-not (Has-Command "git")) {
  if (-not (Install-WithWinget "Git.Git" "Git")) { exit 1 }
  Write-Fix "Can mo lai terminal" "PATH cua Git moi cai co the chua duoc nap vao phien nay." "Dong cua so nay, mo lai run.bat"
  exit 1
}
try {
  Invoke-WebRequest -UseBasicParsing -Uri "https://github.com" -TimeoutSec 8 | Out-Null
} catch {
  Write-Fix "Internet" "Khong truy cap duoc GitHub/pub.dev; pnpm va Flutter co the fail." "Kiem tra VPN/firewall mang roi chay lai run.bat"
}

Write-Step 3 $Total "Kiem tra Python"
if (-not (Has-Command "python")) {
  if (-not (Install-WithWinget "Python.Python.3.12" "Python 3.12")) { exit 1 }
  Write-Fix "Can mo lai terminal" "PATH cua Python moi cai co the chua duoc nap vao phien nay." "Dong cua so nay, mo lai run.bat"
  exit 1
}

Write-Step 4 $Total "Kiem tra Docker Desktop"
if (-not (Has-Command "docker")) {
  if (-not (Install-WithWinget "Docker.DockerDesktop" "Docker Desktop")) { exit 1 }
  Write-Fix "Docker Desktop" "Docker thuong can logout/reboot va mo app lan dau." "Mo Docker Desktop, doi den khi engine san sang, sau do chay lai run.bat"
  exit 1
}
try {
  docker info | Out-Null
} catch {
  Write-Fix "Docker engine" "Docker CLI co nhung Docker Desktop chua chay hoac WSL2 chua san sang." "Mo Docker Desktop, doi den khi Ready, roi chay lai run.bat"
  exit 1
}

Write-Step 5 $Total "Kiem tra Flutter, Android SDK, Java, Codex"
if (-not (Has-Command "flutter")) {
  Write-Fix "Flutter" "Flutter khong bat buoc de mo dashboard, nhung can de build APK." "winget install --id Google.Flutter -e"
}
if (-not (Has-Command "java")) {
  Write-Fix "Java" "Java/JDK can cho Android build." "winget install --id EclipseAdoptium.Temurin.17.JDK -e"
}
if (-not (Has-Command "codex")) {
  Write-Host "Codex CLI chua co. ForgeTrend van chay deterministic mode; co the cai sau bang npm install -g @openai/codex." -ForegroundColor Yellow
}

Write-Step 6 $Total "Kiem tra pnpm/corepack va cai package"
if (-not (Has-Command "pnpm")) {
  if (Has-Command "corepack") {
    corepack enable
    corepack prepare pnpm@latest --activate
  } else {
    npm install -g pnpm
  }
}
pnpm install --frozen-lockfile=false
pnpm setup:python
.\.venv\Scripts\python.exe scripts\ensure_env_secret.py

Write-Step 7 $Total "Khoi dong database"
docker compose up -d postgres redis minio

Write-Step 8 $Total "Chay migration"
pnpm db:migrate

Write-Step 9 $Total "Mo ForgeTrend"
node scripts\bootstrap_common.mjs launch
