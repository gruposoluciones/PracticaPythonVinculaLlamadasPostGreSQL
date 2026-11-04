# Crea (o actualiza) el usuario de la aplicación y actualiza .env.
#
#   .\scripts\crear_usuario_app.ps1
#   .\scripts\crear_usuario_app.ps1 -Usuario vincula
#
# Genera una contraseña aleatoria si no se indica -Password.
# Requiere que la base y el esquema ya existan (.\scripts\inicializar_bd.ps1).
param(
    [string]$Usuario = "vincula",
    [string]$BaseDatos = "",
    [string]$AdminUsuario = "",
    [string]$Password = ""
)

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $PSScriptRoot

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
if (-not $AdminUsuario) { $AdminUsuario = if ($env:DB_ADMIN_USER) { $env:DB_ADMIN_USER } else { "postgres" } }

if ($Usuario -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') { throw "Nombre de usuario no válido." }
if ($BaseDatos -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') { throw "Nombre de base de datos no válido." }

if (-not $Password) {
    $Password = (python -c "import secrets; print(secrets.token_urlsafe(24))").Trim()
}
$passwordSql = $Password.Replace("'", "''")

$psql = (Get-Command psql -ErrorAction SilentlyContinue).Source
if (-not $psql) {
    $candidato = Get-ChildItem "C:\Program Files\PostgreSQL\*\bin\psql.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending |
        Select-Object -First 1
    if ($candidato) { $psql = $candidato.FullName }
}
if (-not $psql) { throw "No se encontró psql.exe." }

if (-not $env:PGPASSWORD) {
    if ($env:DB_ADMIN_PASSWORD) {
        $env:PGPASSWORD = $env:DB_ADMIN_PASSWORD
    } else {
        $seguro = Read-Host "Contraseña de PostgreSQL para '$AdminUsuario'" -AsSecureString
        $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($seguro)
        try {
            $env:PGPASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
        } finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        }
    }
}

$sql = Join-Path $env:TEMP "crear_usuario_app.sql"
@"
DO `$`$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '$Usuario') THEN
    CREATE ROLE $Usuario LOGIN PASSWORD '$passwordSql';
  ELSE
    ALTER ROLE $Usuario WITH LOGIN PASSWORD '$passwordSql';
  END IF;
END
`$`$;
GRANT CONNECT ON DATABASE "$BaseDatos" TO $Usuario;
GRANT USAGE ON SCHEMA public TO $Usuario;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO $Usuario;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO $Usuario;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO $Usuario;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO $Usuario;
"@ | Set-Content -Path $sql -Encoding UTF8

& $psql -U $AdminUsuario -d $BaseDatos -v ON_ERROR_STOP=1 -f $sql 2>&1 | ForEach-Object { Write-Host $_ }
$codigo = $LASTEXITCODE
Remove-Item $sql -Force -ErrorAction SilentlyContinue
if ($codigo -ne 0) { throw "No se pudo crear o actualizar el usuario '$Usuario'." }

# Actualizar .env con las credenciales de la aplicación.
$lineas = @()
if (Test-Path $archivoEnv) { $lineas = Get-Content $archivoEnv }
if ($lineas -match '^DB_USER=') {
    $lineas = $lineas -replace '^DB_USER=.*', "DB_USER=$Usuario"
} else {
    $lineas += "DB_USER=$Usuario"
}
if ($lineas -match '^DB_PASSWORD=') {
    $lineas = $lineas -replace '^DB_PASSWORD=.*', "DB_PASSWORD=$Password"
} else {
    $lineas += "DB_PASSWORD=$Password"
}
[System.IO.File]::WriteAllLines($archivoEnv, $lineas, (New-Object System.Text.UTF8Encoding($false)))

# Verificar la conexión con el nuevo usuario.
$env:PGPASSWORD = $Password
$verificacion = & $psql -U $Usuario -d $BaseDatos -tAc "SELECT current_user" 2>&1
if ($LASTEXITCODE -ne 0) { throw "El usuario '$Usuario' no pudo conectarse: $verificacion" }

$mascara = $Password.Substring(0, 4) + ("*" * ($Password.Length - 8)) + $Password.Substring($Password.Length - 4)
Write-Host "Usuario '$Usuario' listo y .env actualizado." -ForegroundColor Green
Write-Host "Contraseña (guardada en .env): $mascara" -ForegroundColor DarkGray
