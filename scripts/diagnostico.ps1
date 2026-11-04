# Diagnóstico de la instalación. Muestra qué componente falla.
# Uso: .\scripts\diagnostico.ps1
$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = "$raiz\src;$raiz"
$fallos = 0
$advertencias = 0

function Ok($mensaje) { Write-Host "[OK]    $mensaje" -ForegroundColor Green }
function Aviso($mensaje) { Write-Host "[AVISO] $mensaje" -ForegroundColor Yellow; $script:advertencias++ }
function Error($mensaje) { Write-Host "[ERROR] $mensaje" -ForegroundColor Red; $script:fallos++ }

Write-Host "=== Diagnóstico de Vincula ===" -ForegroundColor Cyan
Write-Host "Carpeta: $raiz"

# Python
$version = & python --version 2>&1
if ($LASTEXITCODE -eq 0) { Ok "Python: $version" } else { Error "Python no está disponible en el PATH." }

# Dependencias
$dependencias = & python -c "import pandas, openpyxl, psycopg2, fastapi, uvicorn, dotenv; print('ok')" 2>&1
if ($dependencias -match "ok") {
    Ok "Dependencias de Python instaladas."
} else {
    Error "Faltan dependencias. Ejecuta: pip install -r requirements.txt"
}

# .env
$archivoEnv = Join-Path $raiz ".env"
if (Test-Path $archivoEnv) {
    Ok ".env encontrado."
    Get-Content $archivoEnv | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') {
            $clave = $Matches[1]
            $valor = $Matches[2].Trim('"').Trim("'")
            if (-not [Environment]::GetEnvironmentVariable($clave)) {
                Set-Item -Path "Env:$clave" -Value $valor
            }
        }
    }
} else {
    Error "No existe .env. Copia .env.example a .env y configura DB_PASSWORD."
}

# PostgreSQL
$servicio = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($servicio) {
    if ($servicio.Status -eq "Running") { Ok "Servicio PostgreSQL en ejecución ($($servicio.Name))." }
    else { Error "El servicio PostgreSQL existe pero está detenido." }
} else {
    Error "No se encontró el servicio PostgreSQL."
}

$psql = (Get-Command psql -ErrorAction SilentlyContinue).Source
if (-not $psql) {
    $candidato = Get-ChildItem "C:\Program Files\PostgreSQL\*\bin\psql.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | Select-Object -First 1
    if ($candidato) { $psql = $candidato.FullName }
}
if ($psql) { Ok "psql: $psql" } else { Aviso "psql no está en el PATH (no es imprescindible para la app)." }

# Conexión y tablas con el usuario de la aplicación
$py = Join-Path $env:TEMP "vincula_diagnostico.py"
@'
import sys
from pathlib import Path

sys.path[:0] = [r"__SRC__", r"__RAIZ__"]

try:
    from config.settings import obtener_settings
    from cargadatos.db import cursor

    ajustes = obtener_settings()
    with cursor() as cur:
        cur.execute("SELECT current_user")
        usuario = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM llamadas")
        total = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM etl_cargas")
        cargas = cur.fetchone()[0]
    print(f"ok|{ajustes.db_name}|{usuario}|{total}|{cargas}")
except Exception as exc:
    print(f"error|{type(exc).__name__}: {exc}")
'@.Replace("__SRC__", (Join-Path $raiz "src")).Replace("__RAIZ__", $raiz) |
    Set-Content -Path $py -Encoding UTF8

$resultado = & python $py 2>&1
Remove-Item $py -Force -ErrorAction SilentlyContinue
if ($resultado -match "^ok\|") {
    $partes = $resultado -split "\|"
    Ok "Base de datos '$($partes[1])' accesible como '$($partes[2])' ($($partes[3]) registros, $($partes[4]) cargas)."
} else {
    Error "No se pudo consultar la base de datos: $resultado"
    Error "Revisa .env y ejecuta scripts\crear_usuario_app.ps1 si faltan permisos."
}

# Puerto y API
$escuchando = netstat -ano | Select-String -Pattern "LISTENING" | Select-String -Pattern ":8000\s"
if ($escuchando) {
    Ok "El puerto 8000 está escuchando."
    try {
        $salud = Invoke-RestMethod "http://127.0.0.1:8000/api/salud" -TimeoutSec 5
        if ($salud.base_de_datos) { Ok "La API responde y ve la base de datos." }
        else { Error "La API responde pero no ve la base de datos." }
    } catch {
        Error "El puerto 8000 está ocupado, pero la API no responde: $($_.Exception.Message)"
    }
} else {
    Aviso "La API no está arrancada. Ejecuta .\iniciar.bat o .\scripts\run.ps1."
}

Write-Host ""
if ($fallos -eq 0) {
    Write-Host "Diagnóstico completado sin errores ($advertencias avisos)." -ForegroundColor Green
} else {
    Write-Host "Diagnóstico completado con $fallos error(es) y $advertencias aviso(s)." -ForegroundColor Red
}
exit $fallos
