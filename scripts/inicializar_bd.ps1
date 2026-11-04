# Crea la base de datos (si no existe) y aplica el esquema, índices y vistas.
# Requiere la contraseña en .env (DB_PASSWORD) o en $env:PGPASSWORD.
param(
    [string]$BaseDatos = "",
    [string]$Usuario = ""
)

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $PSScriptRoot

# Leer .env sin sobrescribir variables ya definidas.
$archivoEnv = Join-Path $raiz ".env"
if (Test-Path $archivoEnv) {
    Get-Content $archivoEnv | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') {
            $clave = $Matches[1]
            $valor = $Matches[2].Trim('"').Trim("'")
            if (-not [Environment]::GetEnvironmentVariable($clave)) {
                Set-Item -Path "Env:$clave" -Value $valor
            }
        }
    }
}

if (-not $BaseDatos) { $BaseDatos = if ($env:DB_NAME) { $env:DB_NAME } else { "comunicaciones" } }
if (-not $Usuario) { $Usuario = if ($env:DB_USER) { $env:DB_USER } else { "postgres" } }

if (-not $env:PGPASSWORD -and $env:DB_PASSWORD) {
    $env:PGPASSWORD = $env:DB_PASSWORD
}
if (-not $env:PGPASSWORD) {
    throw "Define DB_PASSWORD en .env o PGPASSWORD en el entorno."
}

$psql = (Get-Command psql -ErrorAction SilentlyContinue).Source
if (-not $psql) {
    $candidato = Get-ChildItem "C:\Program Files\PostgreSQL\*\bin\psql.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending |
        Select-Object -First 1
    if ($candidato) { $psql = $candidato.FullName }
}
if (-not $psql) { throw "No se encontró psql.exe. Instala PostgreSQL o agrégalo al PATH." }

Write-Host "Usando: $psql" -ForegroundColor DarkGray

$existe = & $psql -U $Usuario -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$BaseDatos'"
if ($existe -ne "1") {
    Write-Host "Creando base de datos '$BaseDatos'..." -ForegroundColor Cyan
    & $psql -U $Usuario -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE `"$BaseDatos`""
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear la base de datos." }
} else {
    Write-Host "La base de datos '$BaseDatos' ya existe." -ForegroundColor DarkGray
}

foreach ($archivo in @("001_schema.sql", "002_indexes.sql", "003_views.sql")) {
    $ruta = Join-Path $raiz "sql\$archivo"
    Write-Host "Aplicando $archivo..." -ForegroundColor Cyan
    & $psql -U $Usuario -d $BaseDatos -v ON_ERROR_STOP=1 -f $ruta
    if ($LASTEXITCODE -ne 0) { throw "Error aplicando $archivo" }
}

Write-Host "Base de datos lista." -ForegroundColor Green
