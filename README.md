# Vincula · Consulta local de llamadas

Aplicación **local** para cargar archivos Excel/CSV con registros de comunicaciones en **PostgreSQL**, consultarlos y analizarlos desde una **web HTML** servida en `127.0.0.1`. Ningún dato sale de la máquina.

![Flujo](https://img.shields.io/badge/flujo-Excel%2FCSV%20→%20PostgreSQL%20→%20Web-1d4ed8)

## Qué incluye

- Carga de `.xlsx`, `.xlsm`, `.xls` y `.csv` con **detección inteligente de columnas**.
- Reconoce cabeceras en español e inglés, aunque haya filas de título encima.
- Si no hay cabecera, **infiere las columnas por su contenido** (teléfonos, fechas, horas, IMEI, duración, tipo, sentido).
- **Clasifica los números** como móvil, fijo o extranjero.
- Extrae **IMEI, IMSI, celda, LAC, antena, latitud, longitud, operador, tecnología y roaming**.
- Los campos ausentes o inválidos se guardan como **NULL**.
- Normalización de teléfonos, fechas (incluido serial de Excel), horas (`HHMMSS`, `HH:MM:SS`, fracción del día) y duraciones.
- Carga **idempotente**: recargar el mismo archivo no duplica registros (`hash_fila`).
- Trazabilidad de cada carga en `etl_cargas` (leídas, insertadas, rechazadas, estado).
- Web local con:
  - búsqueda por número, rango de fechas, tipo y sentido;
  - vinculación selectiva entre **2 y 10 líneas**, con matriz de contactos;
  - **módulo Número ↔ IMEI**: todos los IMEIs de un número y todos los números de un IMEI;
  - estadísticas, top destinos y actividad por día;
  - exportación a CSV con todos los campos CDR;
  - carga de archivos desde el navegador.
- API documentada en `http://127.0.0.1:8000/api/docs`.
- 146 tests automatizados de normalización, detección, lectura y filtros.

## Requisitos

| Componente | Versión probada |
|---|---|
| Python | 3.11.9 |
| PostgreSQL | 18.6 (sirve 14+) |
| PowerShell | 5.1 o superior (Windows) |

## Inicio rápido en Windows

**Doble clic en `iniciar.bat`.** El script arranca el servidor y abre el navegador en `http://127.0.0.1:8000`.

Si algo falla, ejecuta:

```powershell
.\scripts\diagnostico.ps1
```

Comprueba Python, dependencias, PostgreSQL, credenciales, tablas, puerto y API, e indica exactamente qué componente está mal.

> No abras `web\index.html` con doble clic: la web necesita la API local. Usa siempre `http://127.0.0.1:8000`.

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
| **Vinculación** | Cruzar de 2 a 10 números seleccionados y ver matriz, pares y comunicaciones |
| **Número ↔ IMEI** | Buscar un número y ver sus IMEIs, o un IMEI y ver sus números |
| **Estadísticas** | Totales, duración, top destinos y actividad diaria |
| **Cargas** | Subir archivos y revisar el historial |

### Consulta de 2 a 10 números

En la pestaña **Vinculación**:

1. Escribe un número y pulsa **Añadir** (o `Enter`).
2. Repite hasta tener entre **2 y 10** números.
3. Pulsa **Consultar**.

La vista muestra:

- las comunicaciones cuyos **dos extremos** están en la selección;
- una **matriz de contactos** por cada par (simétrica, sin diagonal);
- la **participación por número** y los **pares con más contacto**;
- el listado paginado con fecha, hora, duración, tipo y sentido.

Los números se pueden quitar uno a uno con la **×** del chip, o todos con **Limpiar**. El botón *Consultar* se habilita al llegar a 2 y se bloquea al superar 10.

### Número ↔ IMEI

En la pestaña **Número ↔ IMEI**:

1. Elige **Por número** o **Por IMEI**.
2. Escribe el valor y pulsa **Buscar**.
3. Si buscas un número, obtienes todos sus IMEIs con registros, fechas y operadores.
4. Si buscas un IMEI, obtienes todos los números asociados.
5. Puedes hacer clic en un IMEI o en un número para saltar a la búsqueda inversa.

Debajo se listan **todos los pares número-IMEI** registrados, con paginación.

## Detección de columnas

El lector **no depende de posiciones fijas**. Aplica estas estrategias en orden:

1. **Cabecera con sinónimos (español/inglés).** Busca en las primeras 20 filas la que tenga más títulos reconocibles, aunque haya filas de título encima.
2. **Layout legado** de 16/17 columnas (los archivos `entel*.xlsx`).
3. **Inferencia por contenido** si no hay cabecera: perfila cada columna (teléfonos, fechas, horas, IMEI con Luhn, duración, tipo, sentido), descarta columnas réplica y asigna los roles.
4. **Mapeo manual** si el archivo es atípico:

```powershell
.\scripts\cargar.ps1 -Archivo archivo.xlsx --mapeo "titular=0,origen=3,destino=1,fecha=4,hora=13,imei=17,celda=18"
```

### Campos reconocidos

| Campo | Cabeceras de ejemplo |
|---|---|
| `titular` | Línea Titular, MSISDN, Abonado, A-party |
| `origen` | Número origen, Calling Number, Source, From |
| `destino` | Número destino, Called Number, B-party, To |
| `fecha` / `hora` | Fecha, Fechahora, Start Date, Start Time, Timestamp |
| `duracion` | Duración (Segundos), Duration, Call Duration |
| `tipo` | tipo, Call Type, Servicio |
| `sentido` | Entrante/Saliente, Direction, MOC/MTC |
| `imei` / `imsi` | IMEI, IMEISV, IMSI, SIM |
| `celda` / `lac` | Cell ID, Celda, CGI, LAC, TAC |
| `antena` | Site, Antena, BTS, eNodeB, Sector |
| `latitud` / `longitud` | Latitude, Longitude, Lat, Lon |
| `operador` | Operador, Empresa operadora, Carrier |
| `tecnologia` | Technology, RAT, 4G, 5G |
| `roaming` | Roaming, Itinerancia |

Los campos no detectados, vacíos o inválidos se guardan como **NULL**.

### Clasificación de números

Cada número se clasifica como `movil`, `fijo`, `extranjero` o NULL, usando `PAIS_CODIGO` (por defecto `51`, Perú):

- **móvil**: 9 dígitos que empiezan por 9 (con o sin 51);
- **fijo**: 6–8 dígitos nacionales;
- **extranjero**: 10+ dígitos que no empiezan por el código de país.

### Otros formatos

- CSV separado por `;` o `,`.
- Filas de título antes de la cabecera (por ejemplo, `CONSULTA DE LISTA VINCULACIONES`).
- Layout legado de 16 columnas (sin `Número origen`): se cruzan las salientes, pero no las entrantes.

## Modelo de datos

```
etl_cargas 1 ──── * llamadas
```

- `llamadas`: `titular`, `destino`, `origen`, `fecha`, `hora`, `duracion_seg`, `tipo`, `sentido`, `imei`, `imsi`, `celda`, `lac`, `antena`, `latitud`, `longitud`, `operador`, `tecnologia`, `roaming`, `titular_clase`, `origen_clase`, `destino_clase`, `archivo_origen`, `fila_origen`, `hash_fila` (único).
- Todos los campos CDR son opcionales y se guardan como **NULL** cuando faltan.
- `etl_cargas`: archivo, hash SHA-256, formato detectado, contadores y estado.
- Vistas: `v_vinculaciones`, `v_resumen_diario`.
- Los teléfonos se guardan como `TEXT` para no perder ceros ni precisión.

## API

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/salud` | Estado del servidor y la base |
| GET | `/api/resumen` | Totales globales |
| GET | `/api/llamadas` | Listado paginado y filtrado |
| GET | `/api/vinculaciones?numeros=a,b,c` | Comunicaciones, matriz y pares entre 2 y 10 números (también acepta `a` y `b`) |
| GET | `/api/imei/numero?numero=` | IMEIs registrados para un número |
| GET | `/api/imei/equipo?imei=` | Números asociados a un IMEI |
| GET | `/api/imei/pares` | Todos los pares número-IMEI, paginados |
| GET | `/api/estadisticas` | Agregados del conjunto filtrado |
| GET | `/api/agregados?por=dia\|destino\|origen\|tipo\|sentido` | Agrupaciones |
| GET | `/api/cargas` | Historial de cargas |
| POST | `/api/cargar` | Subida de archivo (`multipart/form-data`); acepta `mapeo` opcional |
| GET | `/api/exportar.csv` | Exportación con todos los campos CDR de los filtros actuales |

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
├── src/cargadatos/           # normalización, mapeo, lector, ETL, consultas y API
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

## Preguntas frecuentes (Q&A)

**¿Cuántos números puedo consultar a la vez?**
Entre 2 y 10. El botón *Consultar* se habilita al llegar a 2 y se bloquea por encima de 10.

**¿Puedo cambiar la selección sin recargar la página?**
Sí. Quita números con la **×**, añade otros y vuelve a consultar.

**¿Qué significa la matriz de contactos?**
Cada celda cuenta las comunicaciones entre ese par de números. Es simétrica, la diagonal se excluye y los pares sin contacto muestran `·`.

**¿Qué pasa si un número no aparece en ningún par?**
Aparece con 0 comunicaciones; no se inventan datos.

**¿Por qué una consulta devuelve 0 si el número existe?**
Puede que el archivo no tenga la columna `Número origen`. En ese caso solo se cruzan las comunicaciones salientes (titular → destino).

**¿Cargar el mismo Excel dos veces duplica los registros?**
No. Cada fila tiene un hash único y las repetidas se ignoran; la carga lo informa como *duplicadas*.

**¿Los datos salen de mi PC?**
No. La API y la web escuchan en `127.0.0.1` y la base de datos es local.

**¿Cómo detecta el sistema las columnas?**
Busca una fila de cabecera con sinónimos en español/inglés; si no la encuentra, analiza el contenido de cada columna (teléfonos, fechas, horas, IMEI, duración). También puede forzarse con `--mapeo`.

**¿Cómo distingue móvil, fijo y extranjero?**
Con `PAIS_CODIGO=51`: móvil = 9 dígitos que empiezan por 9; fijo = 6–8 dígitos nacionales; extranjero = 10+ dígitos que no empiezan por 51.

**¿Qué pasa si falta un campo?**
Se guarda como `NULL`, no como cero ni cadena vacía. Solo se rechaza una fila si no tiene ningún número telefónico.

**¿Valida el IMEI?**
Se guarda cualquier IMEI de 14–16 dígitos; para inferir columnas sin cabecera se usa el dígito de control Luhn como señal.

**¿Puedo cargar un archivo con una fila de título antes de la cabecera?**
Sí. El detector busca la cabecera en las primeras 20 filas.

## Verificación funcional (QA)

| Caso | Resultado esperado | Estado |
|---|---|---|
| Cargar `entel_base.xlsx` (17 columnas) | 99 filas insertadas | ✅ |
| Cargar CSV de 16 columnas | Detección automática y carga | ✅ |
| Cargar `renteseg.xlsx` (9 columnas, título + cabecera) | 14/14 filas, sin rechazos | ✅ |
| Recargar el mismo archivo | 0 insertadas, N duplicadas | ✅ |
| Campos ausentes (IMEI, celda, duración…) | Guardados como `NULL` | ✅ |
| Clasificación de números | 99 móviles en los datos de muestra | ✅ |
| Consultar 2 números | Comunicaciones + 1 par | ✅ |
| Consultar 3 números | 75 comunicaciones, 2 pares | ✅ |
| Intentar 1 número | HTTP 400 | ✅ |
| Intentar 11 números | HTTP 400 | ✅ |
| Número `907976887` → IMEIs | 1 IMEI, 1 registro | ✅ |
| IMEI `861731050593753` → números | 4 números, 9 registros | ✅ |
| Clic en un número/IMEI | Cambia a la búsqueda inversa | ✅ |
| Pares número-IMEI | 9 pares paginados | ✅ |
| Exportar CSV | Descarga con BOM, `;` y campos CDR | ✅ |
| Tests automatizados | 147 passed | ✅ |

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
| `Address already in use` | Puerto 8000 ocupado | El script reinicia su propia instancia; si es otro programa, cambia `API_PORT` en `.env` |
| La página carga pero no hay datos | Base vacía o filtros activos | Revisa la pestaña **Cargas** y limpia los filtros |
| Doble clic en `run.ps1` no hace nada | Windows no ejecuta `.ps1` con doble clic | Usa `iniciar.bat` |
| La web se abre en blanco o sin datos | Abriste `web/index.html` directamente | Entra por `http://127.0.0.1:8000` |
| Error inesperado | — | Ejecuta `.\scripts\diagnostico.ps1` y revisa `app.log` |
| Una carga muestra 0 insertadas y N duplicadas | El archivo ya se cargó | Es el comportamiento esperado (idempotencia) |

## Historia

Este proyecto unifica el script original `consulta_vinculaciones.py` (CLI con login) con una solución local completa. El script se conserva en `legacy/` solo como referencia y **no debe usarse**: contiene credenciales en código y columnas que no existen en los archivos actuales.
