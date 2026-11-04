# AGENTS.md

Guía de trabajo para agentes de IA (y personas) en este repositorio.

---

## 1. Qué es este proyecto

Aplicación **local** (sin nube) que:

1. **Carga** archivos Excel (`.xlsx`, `.xlsm`, `.xls`) y CSV con registros de comunicaciones.
2. **Normaliza** y **persiste** los datos en **PostgreSQL**.
3. **Consulta** la información: buscar, filtrar, comparar, vincular líneas y agregar.
4. **La expone** en una **web HTML** servida en `127.0.0.1`.

Todo permanece en la máquina del usuario. No se usan servicios externos, APIs en la nube ni CDNs.

> ⚠️ Los datos son información sensible (tráfico telefónico). No subirlos al repositorio, no incluirlos en logs sin enmascarar y no compartirlos con herramientas de terceros.

---

## 2. Estado actual (implementado)

La solución funciona de punta a punta:

| Componente | Estado |
|---|---|
| Lectura Excel/CSV con detección de layout | ✅ |
| Normalización (teléfonos, fechas, horas, duración) | ✅ |
| Esquema PostgreSQL + índices + vistas | ✅ |
| ETL con trazabilidad e idempotencia (`hash_fila`) | ✅ |
| API FastAPI + frontend HTML | ✅ |
| Subida de archivos desde la web | ✅ |
| Consulta selectiva de 2 a 10 números (matriz y pares) | ✅ |
| Exportación CSV | ✅ |
| 93 tests unitarios | ✅ |

Verificación rápida:

```powershell
.\scripts\pruebas.ps1
.\scripts\inicializar_bd.ps1
.\scripts\cargar.ps1 -Archivo .\data\entrada\entel_base.xlsx
.\scripts\run.ps1   # http://127.0.0.1:8000
```

Los archivos de muestra **no se versionan** (ver `.gitignore`). El script original está en `legacy/` solo como referencia; no se debe usar.

---

## 3. Stack

| Capa | Tecnología | Versión probada |
|---|---|---|
| Runtime | Python | 3.11.9 |
| Excel | pandas + openpyxl | 3.0.3 / 3.1.5 |
| Excel antiguo | xlrd | ≥ 2.0.1 |
| Base de datos | PostgreSQL | 18.6 (sirve 14+) |
| Driver | psycopg2 | 2.9.13 |
| API | FastAPI + uvicorn | 0.162 / ≥ 0.29 |
| Frontend | HTML + CSS + JS vanilla | — |
| Tests | pytest | 9.2 |

Dependencias en `requirements.txt`. No añadir librerías sin justificar y sin actualizar ese archivo.

---

## 4. Estructura

```
.
├── AGENTS.md
├── README.md
├── requirements.txt
├── pyproject.toml            # configuración de pytest y metadatos
├── conftest.py               # añade src/ y la raíz al PYTHONPATH
├── .env.example              # plantilla, sin secretos
├── config/
│   └── settings.py           # variables de entorno + dataclass Settings
├── data/
│   ├── entrada/              # archivos a cargar (ignorado por git)
│   └── procesados/           # archivos ya cargados (ignorado por git)
├── sql/
│   ├── 001_schema.sql
│   ├── 002_indexes.sql
│   └── 003_views.sql
├── src/cargadatos/
│   ├── __init__.py
│   ├── db.py                 # conexión, transacciones, cursor
│   ├── excel_reader.py       # lectura + detección de layout
│   ├── normalizacion.py      # reglas de normalización
│   ├── etl.py                # orquestación + CLI
│   ├── consultas.py          # SQL de negocio
│   └── api.py                # endpoints + frontend estático
├── web/
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── scripts/
│   ├── instalar.ps1
│   ├── inicializar_bd.ps1
│   ├── crear_usuario_app.ps1
│   ├── cargar.ps1
│   ├── run.ps1
│   └── pruebas.ps1
├── legacy/                   # script original, solo referencia
└── tests/
    ├── test_normalizacion.py
    ├── test_excel_reader.py
    └── test_consultas.py
```

No crear archivos fuera de esta estructura sin justificarlo.

---

## 5. Modelo de datos

Base: **`comunicaciones`**, esquema `public`.

### `llamadas`

| Columna | Tipo | Notas |
|---|---|---|
| `id` | `bigserial` PK | |
| `carga_id` | `bigint` FK → `etl_cargas` | `ON DELETE SET NULL` |
| `titular` | `text NOT NULL` | Dígitos, 8–15 (CHECK) |
| `destino` | `text` | Número marcado |
| `origen` | `text` | Número llamante (solo layout de 17 columnas) |
| `fecha` | `date` | |
| `hora` | `time` | |
| `duracion_seg` | `integer NOT NULL` | `CHECK >= 0` |
| `tipo` | `text` | `Voz`, `SMS`, `MMS`, `Datos` |
| `sentido` | `text` | `Entrante`, `Saliente` |
| `archivo_origen` | `text NOT NULL` | |
| `fila_origen` | `integer NOT NULL` | 1-based |
| `hash_fila` | `text NOT NULL UNIQUE` | Idempotencia |

### `etl_cargas`

`id`, `archivo`, `hash_sha256`, `formato`, `filas_leidas`, `filas_insertadas`, `filas_rechazadas`, `estado` (`en_proceso` / `ok` / `error`), `mensaje_error`, `iniciado_en`, `finalizado_en`.

### Vistas

- `v_vinculaciones`: filas con `origen` no nulo.
- `v_resumen_diario`: agregados por fecha.

**Reglas innegociables:** teléfonos en `text`, nunca `bigint`; `hash_fila` único; índices en `(titular,destino)`, `(titular,origen)`, `(origen)`, `(fecha,hora)`.

---

## 6. Formatos de entrada

El lector (`excel_reader.py`) detecta el layout por número de columnas y presencia de cabecera. **No asumir el formato.**

### 17 columnas con cabecera

A `Línea Titular` · B `Número destino` · C réplica de A (ignorar) · D `Número origen` ·
E fecha `YYYYMMDD` · F año · G mes · H día · I fecha `DD/MM/YYYY` ·
J hora `HHMMSS` · K hora · L minuto · M segundo · N hora `HH:MM:SS` ·
O `Duración (Segundos)` · P `tipo` · Q `Entrante/Saliente`.

Formato detectado: `base_17_con_cabecera`.

### 16 columnas (con o sin cabecera)

El mismo layout **sin** `Número origen`. Las posiciones se desplazan:

A titular · B destino · C réplica · D fecha · E año · F mes · G día ·
H fecha alterna · I hora numérica · J hora · K minuto · L segundo ·
M hora texto · N duración · O tipo · P sentido.

Formatos detectados: `sin_origen_16_con_cabecera` / `sin_origen_16_sin_cabecera`.

> En el layout de 16 columnas `origen` queda `NULL`: la UI avisa de que no se pueden cruzar líneas.

### CSV

Se detecta el separador (`;` o `,`) automáticamente con `sep=None`. Mismo criterio de columnas.

### Detección de cabecera

Se considera cabecera si la primera fila contiene etiquetas conocidas o si no incluye ningún valor con 8+ dígitos. Si el archivo no tiene 16 ni 17 columnas → `FormatoNoSoportado` y la carga se marca como error **sin insertar nada**.

---

## 7. Normalización (`normalizacion.py`)

- **Leer todo como texto** (`dtype=str`). Los teléfonos pueden venir como `5.1977369934E10`.
- **Teléfonos:** quitar espacios, guiones, paréntesis y `+`; conservar solo dígitos; 8–15. No truncar. Se conservan ceros iniciales.
- **Fechas:** `YYYYMMDD`, `DD/MM/YYYY`, `YYYY-MM-DD`, `datetime` o serial de Excel (época `1899-12-30`).
- **Horas:** `HHMMSS` (con o sin cero inicial), `H:MM`, `HH:MM:SS`, `time`, `datetime` o fracción del día.
- **Duración:** entero ≥ 0; vacío = 0; negativo o no numérico = fila rechazada.
- **Tipo/sentido:** se normalizan a `Voz`, `SMS`, `MMS`, `Datos` / `Entrante`, `Saliente`.
- **Filas inválidas:** no abortan la carga; se cuentan en `filas_rechazadas` y se guardan hasta 50 motivos.
- **Idempotencia:** `sha256(titular|origen|destino|fecha|hora|duracion|tipo|sentido)`.
- **Logs:** usar `enmascarar()` para teléfonos (`519****9934`).

Cada regla nueva debe tener test en `tests/test_normalizacion.py`.

---

## 8. Comandos

```powershell
# Instalación (crea .venv y .env)
.\scripts\instalar.ps1

# Base de datos
.\scripts\inicializar_bd.ps1
.\scripts\crear_usuario_app.ps1

# Carga
.\scripts\cargar.ps1 -Archivo .\data\entrada\archivo.xlsx
.\scripts\cargar.ps1 -Archivo a.xlsx, b.csv -Mover

# Servidor (API + web)
.\scripts\run.ps1

# Tests
.\scripts\pruebas.ps1
```

Sin scripts:

```powershell
$env:PYTHONPATH = ".\src;."
python -m cargadatos.etl .\data\entrada\archivo.xlsx
python -m uvicorn cargadatos.api:app --host 127.0.0.1 --port 8000 --app-dir src
python -m pytest -q
```

---

## 9. Reglas de implementación

1. **SQL siempre parametrizado** (`%s`). Prohibido concatenar entrada del usuario.
2. **Nunca `SELECT *`** en la API: columnas explícitas.
3. **Paginación obligatoria**; máximo duro de 500 filas (`MAX_FILAS`), exportación máxima 50 000.
4. **Sin credenciales en código**: todo por `.env` / variables de entorno.
5. **No modificar ni borrar** los archivos de `data/entrada`; con `-Mover` pasan a `data/procesados`.
6. **Transacciones**: cada lote de inserción es atómico; si falla, no se inserta nada y `etl_cargas` queda en `error`.
7. **Logging** con `logging` en librerías; `print` solo en la CLI.
8. **Errores**: capturar `psycopg2.Error` y `ValueError`, registrar y devolver mensajes claros (sin trazas en la UI).
9. **Idioma**: nombres de variables, funciones, endpoints y UI en **español**.
10. **Estilo**: PEP 8, type hints en funciones públicas, docstrings breves, ~100 columnas.

---

## 10. Seguridad

- API solo en `127.0.0.1` (nunca `0.0.0.0`).
- `.env` en `.gitignore`; no hay contraseñas en el código.
- La aplicación usa un usuario dedicado (`vincula`) con permisos mínimos; el superusuario solo se usa en los scripts de administración.
- Cabeceras CSP, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Cache-Control: no-store` en `/api/`.
- Validar extensión y tamaño de subida (`MAX_SUBIDA_MB`, por defecto 25).
- No registrar números completos en logs.
- No exponer la base de datos a la red.

---

## 11. Frontend

- HTML/CSS/JS **vanilla**, sin frameworks ni CDN (debe funcionar offline).
- `fetch` a rutas relativas `/api/...`.
- **Prohibido `innerHTML` con datos**: usar `textContent` y `createElement`.
- Validar en cliente **y** en servidor.
- Mostrar estados: cargando, vacío, error y paginación.
- Paginar en servidor; no cargar todo en memoria.
- No usar atributos `style="..."` en el HTML (CSP estricta); si hace falta, asignar `elemento.style.*` desde JS.

---

## 12. Consultas de negocio (`consultas.py`)

1. `listar_llamadas` — filtros + paginación.
2. `vincular_varios` — comunicaciones entre 2 y 10 líneas; devuelve matriz de pares, participación por número y listado paginado. `vincular(a, b)` se mantiene como compatibilidad.
3. `estadisticas` — totales, duración, voz/SMS, entrantes/salientes, días, líneas.
4. `agregados` — por día, destino, origen, tipo o sentido.
5. `exportar_filas` — CSV con tope.
6. `obtener_resumen` — indicadores globales + última carga.
7. `listar_cargas` — historial.

Toda consulta nueva debe tener índice que la soporte y un test (o justificación de por qué no lo tiene).

---

## 13. Tests y criterios de aceptación

```powershell
.\scripts\pruebas.ps1
```

Los tests actuales **no requieren base de datos** (normalización, lector y filtros). Si se añaden tests de integración, deben omitirse con `pytest.mark.skipif` cuando no haya `DB_PASSWORD`.

Criterios:

- [x] `.xls`, `.xlsx` y `.csv` con detección automática.
- [x] Recargar no duplica (`hash_fila`).
- [x] Teléfonos exactos, sin notación científica ni ceros perdidos.
- [x] Filas inválidas contadas y logueadas, sin abortar.
- [x] Web con búsqueda, filtros, paginación y exportación.
- [x] Consulta selectiva de 2 a 10 números con matriz de contactos.
- [x] Sin credenciales ni datos en el repositorio.
- [x] `pytest` en verde.

---

## 14. Anti-patrones

- ❌ Guardar teléfonos como `bigint`.
- ❌ Leer Excel con `dtype` por defecto y confiar en la inferencia de pandas.
- ❌ Asumir que todos los archivos tienen las mismas columnas.
- ❌ `f"SELECT ... WHERE titular = '{numero}'"`.
- ❌ Cargar un Excel completo en memoria y renderizarlo entero en el HTML.
- ❌ Subir `data/`, `.env` o `*.log` a git.
- ❌ Exponer la API en `0.0.0.0`.
- ❌ Reintroducir el login con SHA-256 del script legacy.
