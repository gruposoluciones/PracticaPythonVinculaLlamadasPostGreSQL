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
| Lectura Excel/CSV con detección inteligente de columnas | ✅ |
| Detección de cabecera con sinónimos ES/EN (y filas de título) | ✅ |
| Inferencia de columnas por contenido si no hay cabecera | ✅ |
| Normalización (teléfonos, fechas, horas, duración) | ✅ |
| Clasificación de números (móvil/fijo/extranjero) | ✅ |
| Campos CDR ampliados (IMEI, IMSI, celda, LAC, antena, GPS…) | ✅ |
| Campos ausentes guardados como NULL | ✅ |
| Esquema PostgreSQL + índices + vistas | ✅ |
| ETL con trazabilidad e idempotencia (`hash_fila`) | ✅ |
| API FastAPI + frontend HTML | ✅ |
| Subida de archivos desde la web | ✅ |
| Consulta selectiva de 2 a 10 números (matriz y pares) | ✅ |
| Exportación CSV | ✅ |
| 146 tests unitarios | ✅ |

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
│   ├── 003_views.sql
│   └── 004_cdr_extendido.sql  # migración de bases anteriores
├── src/cargadatos/
│   ├── __init__.py
│   ├── db.py                 # conexión, transacciones, cursor
│   ├── mapeo.py              # detección de columnas CDR
│   ├── excel_reader.py       # lectura + cabecera/inferencia
│   ├── normalizacion.py      # reglas de normalización y clasificación
│   ├── etl.py                # orquestación + CLI
│   ├── mantenimiento.py      # reclasificación de datos existentes
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
│   ├── reclasificar.ps1
│   ├── run.ps1
│   └── pruebas.ps1
├── legacy/                   # script original, solo referencia
└── tests/
    ├── test_normalizacion.py
    ├── test_mapeo.py
    ├── test_excel_reader.py
    ├── test_etl.py
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
| `origen` | `text` | Número llamante |
| `fecha` | `date` | NULL si no venía |
| `hora` | `time` | NULL si no venía |
| `duracion_seg` | `integer` | `CHECK >= 0`; NULL si no venía |
| `tipo` | `text` | `Voz`, `SMS`, `MMS`, `Datos` |
| `sentido` | `text` | `Entrante`, `Saliente` |
| `imei` | `text` | 14–16 dígitos |
| `imsi` | `text` | 14–16 dígitos |
| `celda` / `lac` | `text` | Cell ID / LAC o TAC |
| `antena` | `text` | Site, BTS, eNodeB, sector |
| `latitud` / `longitud` | `numeric(9,6)` | Rango validado |
| `operador` | `text` | Empresa operadora |
| `tecnologia` | `text` | 2G/3G/4G/5G, RAT |
| `roaming` | `boolean` | NULL si no se informa |
| `titular_clase` | `text` | `movil`, `fijo`, `extranjero` o NULL |
| `origen_clase` | `text` | Igual |
| `destino_clase` | `text` | Igual |
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

## 6. Detección de columnas

El lector (`mapeo.py` + `excel_reader.py`) aplica estas estrategias, en orden:

1. **Cabecera con sinónimos ES/EN.** Busca entre las primeras 20 filas la que tenga más títulos reconocibles, aunque haya filas de título encima. Ejemplos: `MSISDN`, `Abonado`, `A-party` → `titular`; `Called Number`, `B-party`, `To` → `destino`; `Calling Number`, `Source` → `origen`; `Fechahora`, `Start Date` → `fecha`; `Cell ID`, `CGI` → `celda`; `Site`, `BTS`, `eNodeB` → `antena`; `Empresa operadora` → `operador`.
2. **Layout legado de 17/16 columnas** (`legacy_17_*`, `legacy_16_*`).
3. **Inferencia por contenido** (`cdr_inferido`): perfila cada columna (teléfonos, fechas, horas, IMEI con Luhn, duración, tipo, sentido), descarta columnas réplica y asigna los roles.
4. **Mapeo manual** (`manual`) cuando el archivo es atípico:

```powershell
.\scripts\cargar.ps1 -Archivo archivo.xlsx --mapeo "titular=0,origen=3,destino=1,fecha=4,hora=13,imei=17,celda=18"
```

Formatos detectados: `cdr_con_cabecera`, `cdr_inferido`, `legacy_17_con_cabecera`, `legacy_16_con_cabecera`, `legacy_17_sin_cabecera`, `legacy_16_sin_cabecera`, `manual`.

Si no se identifica ninguna columna de número → `FormatoNoSoportado` y no se inserta nada.

> La inferencia sin cabecera es heurística. Para CDR atípicos, usar `--mapeo` y añadir un test con ese layout.

### Clasificación de números

`clasificar_telefono(numero, codigo_pais)` devuelve `movil`, `fijo`, `extranjero` o NULL. Usa `PAIS_CODIGO` (51 por defecto) y se aplica a `titular`, `origen` y `destino`.

### Campos opcionales

Todos los campos CDR salvo `titular` pueden quedar en NULL. Una fila solo se rechaza cuando no contiene ningún número utilizable; la falta de fecha, hora, duración, IMEI o celda no la invalida.

---

## 7. Normalización (`normalizacion.py`)

- **Leer todo como texto** (`dtype=str`). Los teléfonos pueden venir como `5.1977369934E10`.
- **Teléfonos:** quitar espacios, guiones, paréntesis y `+`; conservar solo dígitos; 8–15. No truncar. Se conservan ceros iniciales.
- **Fechas:** `YYYYMMDD`, `DD/MM/YYYY`, `YYYY-MM-DD`, `datetime` o serial de Excel (época `1899-12-30`, limitado a 1900–2100 para no confundir horas).
- **Horas:** `HHMMSS` (con o sin cero inicial), `H:MM`, `HH:MM:SS`, `time`, `datetime` o fracción del día. Acepta `fechahora` combinada (`2026-06-13 12:02:23`).
- **Componentes:** si no hay fecha/hora completa, se construyen con año/mes/día y hora/minuto/segundo.
- **Duración:** entero ≥ 0; vacío o inválido → **NULL**.
- **Tipo/sentido:** `Voz`, `SMS`, `MMS`, `Datos`, `USSD` / `Entrante`, `Saliente`. Si falta el sentido, se deduce de titular/origen/destino.
- **IMEI:** 14–16 dígitos; `es_imei_valido` (Luhn) solo se usa para inferir columnas.
- **IMSI:** 14–16 dígitos. **Celda/LAC/antena/operador/tecnología:** texto.
- **Coordenadas:** latitud −90..90, longitud −180..180; fuera de rango → NULL.
- **Roaming:** booleano (`si/no`, `1/0`, `true/false`); desconocido → NULL.
- **Clasificación:** `clasificar_telefono` aplica `PAIS_CODIGO` a titular, origen y destino.
- **Filas inválidas:** solo se rechazan las que no tienen ningún número; se cuentan en `filas_rechazadas` y se guardan hasta 50 motivos.
- **Idempotencia:** `sha256` de los campos clave; si hay IMEI/celda/antena se añaden al hash para no colapsar registros distintos (los hashes antiguos sin estos campos no cambian).
- **Logs:** usar `enmascarar()` para teléfonos (`519****9934`).

Cada regla nueva debe tener test en `tests/test_normalizacion.py` o `tests/test_etl.py`.

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
.\scripts\cargar.ps1 -Archivo atipico.xlsx --mapeo "titular=0,origen=3,destino=1,fecha=4,hora=13"

# Reclasificar números ya cargados (móvil/fijo/extranjero)
.\scripts\reclasificar.ps1

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
3. `estadisticas` — totales, duración, voz/SMS, entrantes/salientes, móviles/fijos/extranjeros, IMEI/celda informados, días y líneas.
4. `agregados` — por día, destino, origen, tipo o sentido.
5. `exportar_filas` — CSV con tope y todos los campos CDR.
6. `obtener_resumen` — indicadores globales + última carga.
7. `listar_cargas` — historial.
8. `normalizar_registro` (en `etl.py`) — normalización de una fila; es la función que usan los tests de campos NULL y clasificación.

Toda consulta nueva debe tener índice que la soporte y un test (o justificación de por qué no lo tiene).

---

## 13. Tests y criterios de aceptación

```powershell
.\scripts\pruebas.ps1
```

Los tests actuales **no requieren base de datos** (normalización, lector y filtros). Si se añaden tests de integración, deben omitirse con `pytest.mark.skipif` cuando no haya `DB_PASSWORD`.

Criterios:

- [x] `.xls`, `.xlsx` y `.csv` con detección inteligente de columnas.
- [x] Cabecera con sinónimos ES/EN y filas de título antes de la cabecera.
- [x] Inferencia por contenido cuando no hay cabecera y mapeo manual disponible.
- [x] Clasificación móvil/fijo/extranjero y campos CDR ampliados.
- [x] Campos ausentes guardados como NULL.
- [x] Recargar no duplica (`hash_fila`).
- [x] Teléfonos exactos, sin notación científica ni ceros perdidos.
- [x] Filas inválidas contadas y logueadas, sin abortar.
- [x] Web con búsqueda, filtros, paginación y exportación.
- [x] Consulta selectiva de 2 a 10 números con matriz de contactos.
- [x] Sin credenciales ni datos en el repositorio.
- [x] `pytest` en verde (146 tests).

---

## 14. Anti-patrones

- ❌ Guardar teléfonos como `bigint`.
- ❌ Leer Excel con `dtype` por defecto y confiar en la inferencia de pandas.
- ❌ Asumir que todos los archivos tienen las mismas columnas.
- ❌ Mapear columnas solo por posición cuando hay cabecera reconocible.
- ❌ Inventar valores para campos ausentes: deben ser NULL.
- ❌ `f"SELECT ... WHERE titular = '{numero}'"`.
- ❌ Cargar un Excel completo en memoria y renderizarlo entero en el HTML.
- ❌ Subir `data/`, `.env` o `*.log` a git.
- ❌ Exponer la API en `0.0.0.0`.
- ❌ Reintroducir el login con SHA-256 del script legacy.
