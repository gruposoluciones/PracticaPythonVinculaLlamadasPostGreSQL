# Recalcula la clasificación de números existentes (móvil/fijo/extranjero).
$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = "$raiz\src;$raiz"
& python -m cargadatos.mantenimiento @args 2>&1 | ForEach-Object { Write-Host $_ }
exit $LASTEXITCODE
