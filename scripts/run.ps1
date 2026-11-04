# Arranca la API y el frontend en http://127.0.0.1:8000
$ErrorActionPreference = "Continue"

$raiz = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = "$raiz\src;$raiz"

$hostApi = "127.0.0.1"
$puerto = 8000
$archivoEnv = Join-Path $raiz ".env"

if (Test-Path $archivoEnv) {
    Get-Content $archivoEnv | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') {
            $clave = $Matches[1]
            $valor = $Matches[2].Trim('"').Trim("'")
            if ($clave -eq "API_HOST" -and $valor) { $hostApi = $valor }
            if ($clave -eq "API_PORT" -and $valor) { $puerto = [int]$valor }
        }
    }
}

Write-Host "Iniciando Vincula en http://${hostApi}:${puerto}" -ForegroundColor Cyan
Write-Host "Pulsa Ctrl+C para detener." -ForegroundColor DarkGray

& python -m uvicorn cargadatos.api:app --host $hostApi --port $puerto --app-dir "$raiz\src"
