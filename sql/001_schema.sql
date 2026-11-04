-- Esquema base de la aplicación.
-- Ejecutar sobre la base de datos "comunicaciones".

CREATE TABLE IF NOT EXISTS etl_cargas (
    id                BIGSERIAL PRIMARY KEY,
    archivo           TEXT        NOT NULL,
    hash_sha256       TEXT        NOT NULL,
    formato           TEXT        NOT NULL,
    filas_leidas      INTEGER     NOT NULL DEFAULT 0,
    filas_insertadas  INTEGER     NOT NULL DEFAULT 0,
    filas_rechazadas  INTEGER     NOT NULL DEFAULT 0,
    estado            TEXT        NOT NULL DEFAULT 'en_proceso'
                      CHECK (estado IN ('en_proceso', 'ok', 'error')),
    mensaje_error     TEXT,
    iniciado_en       TIMESTAMPTZ NOT NULL DEFAULT now(),
    finalizado_en     TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS llamadas (
    id             BIGSERIAL PRIMARY KEY,
    carga_id       BIGINT REFERENCES etl_cargas (id) ON DELETE SET NULL,
    titular        TEXT        NOT NULL,
    destino        TEXT,
    origen         TEXT,
    fecha          DATE,
    hora           TIME,
    duracion_seg   INTEGER     CHECK (duracion_seg IS NULL OR duracion_seg >= 0),
    tipo           TEXT,
    sentido        TEXT,
    imei           TEXT,
    imsi           TEXT,
    celda          TEXT,
    lac            TEXT,
    antena         TEXT,
    latitud        NUMERIC(9, 6),
    longitud       NUMERIC(9, 6),
    operador       TEXT,
    tecnologia     TEXT,
    roaming        BOOLEAN,
    titular_clase  TEXT,
    origen_clase   TEXT,
    destino_clase  TEXT,
    archivo_origen TEXT        NOT NULL,
    fila_origen    INTEGER     NOT NULL,
    hash_fila      TEXT        NOT NULL UNIQUE,
    creado_en      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT llamadas_titular_digitos CHECK (titular ~ '^[0-9]{8,15}$'),
    CONSTRAINT llamadas_origen_digitos  CHECK (origen  IS NULL OR origen  ~ '^[0-9]{8,15}$'),
    CONSTRAINT llamadas_destino_digitos CHECK (destino IS NULL OR destino ~ '^[0-9]{8,15}$'),
    CONSTRAINT llamadas_titular_clase   CHECK (titular_clase IS NULL OR titular_clase IN ('movil', 'fijo', 'extranjero', 'desconocido')),
    CONSTRAINT llamadas_origen_clase    CHECK (origen_clase  IS NULL OR origen_clase  IN ('movil', 'fijo', 'extranjero', 'desconocido')),
    CONSTRAINT llamadas_destino_clase   CHECK (destino_clase IS NULL OR destino_clase IN ('movil', 'fijo', 'extranjero', 'desconocido')),
    CONSTRAINT llamadas_latitud_rango   CHECK (latitud  IS NULL OR latitud  BETWEEN -90 AND 90),
    CONSTRAINT llamadas_longitud_rango  CHECK (longitud IS NULL OR longitud BETWEEN -180 AND 180)
);

-- Actualiza bases creadas con versiones anteriores (idempotente).
ALTER TABLE llamadas
    ADD COLUMN IF NOT EXISTS imei          TEXT,
    ADD COLUMN IF NOT EXISTS imsi          TEXT,
    ADD COLUMN IF NOT EXISTS celda         TEXT,
    ADD COLUMN IF NOT EXISTS lac           TEXT,
    ADD COLUMN IF NOT EXISTS antena        TEXT,
    ADD COLUMN IF NOT EXISTS latitud       NUMERIC(9, 6),
    ADD COLUMN IF NOT EXISTS longitud      NUMERIC(9, 6),
    ADD COLUMN IF NOT EXISTS operador      TEXT,
    ADD COLUMN IF NOT EXISTS tecnologia    TEXT,
    ADD COLUMN IF NOT EXISTS roaming       BOOLEAN,
    ADD COLUMN IF NOT EXISTS titular_clase TEXT,
    ADD COLUMN IF NOT EXISTS origen_clase  TEXT,
    ADD COLUMN IF NOT EXISTS destino_clase TEXT;

ALTER TABLE llamadas ALTER COLUMN duracion_seg DROP NOT NULL;
ALTER TABLE llamadas ALTER COLUMN duracion_seg DROP DEFAULT;

COMMENT ON TABLE llamadas IS 'Registros de comunicación normalizados (CDR).';
COMMENT ON COLUMN llamadas.hash_fila IS 'SHA-256 de los campos clave; evita duplicados.';
COMMENT ON COLUMN llamadas.archivo_origen IS 'Nombre del archivo del que proviene la fila.';
COMMENT ON COLUMN llamadas.fila_origen IS 'Número de fila (1-based) en el archivo original.';
COMMENT ON COLUMN llamadas.duracion_seg IS 'Duración en segundos; NULL si el campo no venía.';
COMMENT ON COLUMN llamadas.titular_clase IS 'movil, fijo, extranjero o NULL.';
COMMENT ON COLUMN llamadas.imei IS 'IMEI/IMEISV validado con Luhn cuando tiene 15 dígitos.';
