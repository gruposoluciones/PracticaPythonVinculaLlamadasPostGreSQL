# Crea un entorno virtual e instala las dependencias.
$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $raiz ".venv"

if (-not (Test-Path $venv)) {
    Write-Host "Creando entorno virtual..." -ForegroundColor Cyan
    python -m venv $venv
}

$python = Join-Path $venv "Scripts\python.exe"
& $python -m pip install --upgrade pip
& $python -m pip install -r (Join-Path $raiz "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Falló la instalación de dependencias." }

if (-not (Test-Path (Join-Path $raiz ".env"))) {
    Copy-Item (Join-Path $raiz ".env.example") (Join-Path $raiz ".env")
    Write-Host "Se creó .env a partir de .env.example. Edita DB_PASSWORD." -ForegroundColor Yellow
}

Write-Host "Entorno listo. Actívalo con: .\.venv\Scripts\Activate.ps1" -ForegroundColor Green
