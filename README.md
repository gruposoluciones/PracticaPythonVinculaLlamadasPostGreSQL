# Vincula · Consulta local de llamadas

Aplicación **local** para cargar archivos Excel/CSV con registros de comunicaciones en **PostgreSQL**, consultarlos y analizarlos desde una **web HTML** servida en `127.0.0.1`. Ningún dato sale de la máquina.

![Flujo](https://img.shields.io/badge/flujo-Excel%2FCSV%20→%20PostgreSQL%20→%20Web-1d4ed8)

## Qué incluye

- Carga de `.xlsx`, `.xlsm`, `.xls` y `.csv` con **detección automática de formato**.
- Normalización de teléfonos, fechas (incluido serial de Excel), horas (`HHMMSS`, `HH:MM:SS`, fracción del día) y duraciones.
- Carga **idempotente**: recargar el mismo archivo no duplica registros (`hash_fila`).
- Trazabilidad de cada carga en `etl_cargas` (leídas, insertadas, rechazadas, estado).
- Web local con:
  - búsqueda por número, rango de fechas, tipo y sentido;
  - vinculación entre dos líneas;
  - estadísticas, top destinos y actividad por día;
  - exportación a CSV;
  - carga de archivos desde el navegador.
- API documentada en `http://127.0.0.1:8000/api/docs`.
- 83 tests automatizados de normalización, lectura y filtros.

## Requisitos

| Componente | Versión probada |
|---|---|
| Python | 3.11.9 |
| PostgreSQL | 18.6 (sirve 14+) |
| PowerShell | 5.1 o superior (Windows) |

## Instalación rápida

```powershell
# 1. Dependencias (crea .venv y .env)
.\scripts\instalar.ps1

# 2. Ajusta .env si tu PostgreSQL no está en localhost:5432
notepad .env

# 3. Crea la base y aplica el esquema (pide la contraseña de postgres)
.\scripts\inicializar_bd.ps1

# 4. Crea el usuario de la aplicación y guarda su contraseña en .env
.\scripts\crear_usuario_app.ps1

# 5. Coloca tus archivos en data\entrada y cárgalos
.\scripts\cargar.ps1 -Archivo .\data\entrada\entel_base.xlsx

# 6. Arranca la aplicación
.\scripts\run.ps1
```

Abre **http://127.0.0.1:8000**.

> Si prefieres no usar entorno virtual: `pip install -r requirements.txt` y ejecuta los scripts igualmente. `inicializar_bd.ps1` localiza `psql.exe` automáticamente si no está en el `PATH`.

## Uso

### Cargar archivos

**Desde la web:** pestaña **Cargas** → selecciona el archivo → *Cargar en PostgreSQL*.

**Desde la consola:**

```powershell
.\scripts\cargar.ps1 -Archivo .\data\entrada\archivo.xlsx
.\scripts\cargar.ps1 -Archivo a.xlsx, b.csv -Mover
```

`-Mover` traslada el archivo a `data\procesados` cuando la carga termina bien.

### Consultar

| Pestaña | Para qué sirve |
|---|---|
| **Consulta** | Filtrar por número, fechas, tipo y sentido; paginar y exportar |
| **Vinculación** | Ver todas las comunicaciones entre dos líneas |
| **Estadísticas** | Totales, duración, top destinos y actividad diaria |
| **Cargas** | Subir archivos y revisar el historial |

## Formatos soportados

El lector detecta el layout por el número de columnas y la presencia de cabecera.

**17 columnas con cabecera** (`entel_base.xlsx`): incluye `Número origen`.

| Col | Campo |
|---|---|
| A | Línea titular |
| B | Número destino |
| C | (réplica de A, se ignora) |
| D | Número origen |
| E–I | Fecha (numérica, partes y texto) |
| J–N | Hora (numérica, partes y texto) |
| O | Duración en segundos |
| P | Tipo |
| Q | Entrante/Saliente |

**16 columnas** (con o sin cabecera): el mismo layout **sin** `Número origen`.
En ese caso las consultas de vinculación avisan de que no hay origen que cruzar.

También se acepta CSV separado por `;` o `,`.

## Modelo de datos

```
etl_cargas 1 ──── * llamadas
```

- `llamadas`: `titular`, `destino`, `origen`, `fecha`, `hora`, `duracion_seg`, `tipo`, `sentido`, `archivo_origen`, `fila_origen`, `hash_fila` (único).
- `etl_cargas`: archivo, hash SHA-256, formato detectado, contadores y estado.
- Vistas: `v_vinculaciones`, `v_resumen_diario`.
- Los teléfonos se guardan como `TEXT` para no perder ceros ni precisión.

## API

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/salud` | Estado del servidor y la base |
| GET | `/api/resumen` | Totales globales |
| GET | `/api/llamadas` | Listado paginado y filtrado |
| GET | `/api/vinculaciones?a=&b=` | Comunicaciones entre dos líneas |
| GET | `/api/estadisticas` | Agregados del conjunto filtrado |
| GET | `/api/agregados?por=dia\|destino\|origen\|tipo\|sentido` | Agrupaciones |
| GET | `/api/cargas` | Historial de cargas |
| POST | `/api/cargar` | Subida de archivo (`multipart/form-data`) |
| GET | `/api/exportar.csv` | Exportación de los filtros actuales |

Parámetros comunes: `numero`, `desde`, `hasta`, `tipo`, `sentido`, `parcial`, `pagina`, `tamano`.

## Estructura

```
.
├── config/settings.py        # configuración por variables de entorno
├── data/entrada/             # archivos a cargar (no versionado)
├── data/procesados/          # archivos ya cargados (no versionado)
├── legacy/                   # script original, solo referencia
├── scripts/                  # instalar, crear BD, cargar, arrancar, tests
├── sql/                      # esquema, índices y vistas
├── src/cargadatos/           # normalización, lector, ETL, consultas y API
├── tests/                    # pruebas unitarias
├── web/                      # frontend HTML/CSS/JS
├── AGENTS.md                 # convenciones para agentes
└── requirements.txt
```

## Tests

```powershell
.\scripts\pruebas.ps1
# o
python -m pytest -q
```

## Seguridad y datos

- La web y la API escuchan **solo en `127.0.0.1`**.
- La aplicación usa un usuario dedicado (`vincula`) con permisos mínimos; el superusuario solo se usa en los scripts de administración.
- Las credenciales viven en `.env`, que está en `.gitignore`.
- Las consultas usan parámetros (`%s`); no se concatena entrada del usuario.
- La exportación tiene un tope de 50 000 filas y los listados de 500 por página.
- Cabeceras CSP, `X-Frame-Options`, `nosniff` y `no-store`.
- Los archivos de datos y los logs **no se versionan**.

> Los registros de tráfico telefónico son información sensible. No subas `data/` ni `.env` a ningún repositorio, y no compartas la carpeta del proyecto sin anonimizar.

## Solución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| `Falta DB_PASSWORD` | No existe `.env` | `Copy-Item .env.example .env` y edita el valor |
| `permission denied for table llamadas` | El usuario de la app no tiene permisos | Ejecuta `.\scripts\crear_usuario_app.ps1` |
| `No se encontró psql.exe` | PostgreSQL no está en `PATH` | Instala PostgreSQL o agrega `bin` al `PATH` |
| `password authentication failed` | Contraseña incorrecta | Revisa `.env` o vuelve a ejecutar `crear_usuario_app.ps1` |
| `Address already in use` | Puerto 8000 ocupado | Cambia `API_PORT` en `.env` |
| Una carga muestra 0 insertadas y N duplicadas | El archivo ya se cargó | Es el comportamiento esperado (idempotencia) |

## Historia

Este proyecto unifica el script original `consulta_vinculaciones.py` (CLI con login) con una solución local completa. El script se conserva en `legacy/` solo como referencia y **no debe usarse**: contiene credenciales en código y columnas que no existen en los archivos actuales.
