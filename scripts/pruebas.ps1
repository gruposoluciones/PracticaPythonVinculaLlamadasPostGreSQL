# Ejecuta la batería de tests.
$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = "$raiz\src;$raiz"
& python -m pytest @args 2>&1 | ForEach-Object { Write-Host $_ }
exit $LASTEXITCODE
