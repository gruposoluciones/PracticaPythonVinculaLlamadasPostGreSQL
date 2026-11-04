# Carga uno o varios archivos Excel/CSV en PostgreSQL.
# Ejemplo:
#   .\scripts\cargar.ps1 -Archivo ..\data\entrada\entel_base.xlsx
#   .\scripts\cargar.ps1 -Archivo a.xlsx, b.csv -Mover
param(
    [Parameter(Mandatory = $true, ValueFromRemainingArguments = $true)]
    [string[]]$Archivo,
    [switch]$Mover,
    [switch]$Detalle
)

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = "$raiz\src;$raiz"

$argumentos = @()
foreach ($ruta in $Archivo) {
    $argumentos += (Resolve-Path $ruta).Path
}
if ($Mover) { $argumentos += "--mover" }
if ($Detalle) { $argumentos += "--verbose" }

& python -m cargadatos.etl @argumentos 2>&1 | ForEach-Object { Write-Host $_ }
exit $LASTEXITCODE
