# Arranca la API y el frontend en http://127.0.0.1:8000
# Uso: .\scripts\run.ps1 [-NoAbrir]
param(
    [switch]$NoAbrir
)

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

$url = "http://${hostApi}:${puerto}"

function Abrir-Navegador {
    if ($NoAbrir) { return }
    Start-Process -FilePath "powershell" -ArgumentList @(
        "-NoProfile",
        "-WindowStyle", "Hidden",
        "-Command", "Start-Sleep -Seconds 2; Start-Process '$url'"
    ) -WindowStyle Hidden | Out-Null
}

# Si el puerto está ocupado por una instancia anterior de esta app, se reinicia.
$escuchando = netstat -ano | Select-String -Pattern "LISTENING" | Select-String -Pattern ":$puerto\s"
foreach ($linea in $escuchando) {
    $procId = ($linea.ToString().Trim() -split '\s+')[-1]
    $proceso = Get-CimInstance Win32_Process -Filter "ProcessId = $procId" -ErrorAction SilentlyContinue
    $comando = if ($proceso) { [string]$proceso.CommandLine } else { "" }
    if ($comando -match "uvicorn" -and $comando -match "cargadatos") {
        Write-Host "Deteniendo una instancia anterior de Vincula (PID $procId)..." -ForegroundColor Yellow
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    } else {
        Write-Host "El puerto $puerto está ocupado por otro proceso ($($proceso.Name))." -ForegroundColor Red
        Write-Host "Cambia API_PORT en .env o cierra ese proceso." -ForegroundColor Red
        exit 1
    }
}

Write-Host "Iniciando Vincula en $url" -ForegroundColor Cyan
Write-Host "Pulsa Ctrl+C para detener." -ForegroundColor DarkGray

Abrir-Navegador

& python -m uvicorn cargadatos.api:app --host $hostApi --port $puerto --app-dir "$raiz\src"
