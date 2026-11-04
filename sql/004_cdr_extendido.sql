-- Migración para bases creadas con la versión anterior (CDR ampliado).
-- Es idempotente: se puede ejecutar varias veces.

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

-- Los campos ausentes ahora se guardan como NULL (antes duración usaba 0).
ALTER TABLE llamadas ALTER COLUMN duracion_seg DROP NOT NULL;
ALTER TABLE llamadas ALTER COLUMN duracion_seg DROP DEFAULT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'llamadas_latitud_rango'
    ) THEN
        ALTER TABLE llamadas
            ADD CONSTRAINT llamadas_latitud_rango
            CHECK (latitud IS NULL OR latitud BETWEEN -90 AND 90);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'llamadas_longitud_rango'
    ) THEN
        ALTER TABLE llamadas
            ADD CONSTRAINT llamadas_longitud_rango
            CHECK (longitud IS NULL OR longitud BETWEEN -180 AND 180);
    END IF;
END
$$;

COMMENT ON COLUMN llamadas.duracion_seg IS 'Duración en segundos; NULL si el campo no venía.';
COMMENT ON COLUMN llamadas.titular_clase IS 'movil, fijo, extranjero o NULL.';
COMMENT ON COLUMN llamadas.imei IS 'IMEI/IMEISV validado con Luhn cuando tiene 15 dígitos.';
