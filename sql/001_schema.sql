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
    duracion_seg   INTEGER     NOT NULL DEFAULT 0 CHECK (duracion_seg >= 0),
    tipo           TEXT,
    sentido        TEXT,
    archivo_origen TEXT        NOT NULL,
    fila_origen    INTEGER     NOT NULL,
    hash_fila      TEXT        NOT NULL UNIQUE,
    creado_en      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT llamadas_titular_digitos CHECK (titular ~ '^[0-9]{8,15}$'),
    CONSTRAINT llamadas_origen_digitos  CHECK (origen  IS NULL OR origen  ~ '^[0-9]{8,15}$'),
    CONSTRAINT llamadas_destino_digitos CHECK (destino IS NULL OR destino ~ '^[0-9]{8,15}$')
);

COMMENT ON TABLE llamadas IS 'Registros de comunicación normalizados.';
COMMENT ON COLUMN llamadas.hash_fila IS 'SHA-256 de los campos clave; evita duplicados.';
COMMENT ON COLUMN llamadas.archivo_origen IS 'Nombre del archivo del que proviene la fila.';
COMMENT ON COLUMN llamadas.fila_origen IS 'Número de fila (1-based) en el archivo original.';
