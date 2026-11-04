-- Índices para las consultas de la aplicación.

CREATE INDEX IF NOT EXISTS idx_llamadas_titular_destino
    ON llamadas (titular, destino);

CREATE INDEX IF NOT EXISTS idx_llamadas_titular_origen
    ON llamadas (titular, origen);

CREATE INDEX IF NOT EXISTS idx_llamadas_origen
    ON llamadas (origen);

CREATE INDEX IF NOT EXISTS idx_llamadas_destino
    ON llamadas (destino);

CREATE INDEX IF NOT EXISTS idx_llamadas_fecha_hora
    ON llamadas (fecha DESC, hora DESC);

CREATE INDEX IF NOT EXISTS idx_llamadas_tipo
    ON llamadas (tipo);

CREATE INDEX IF NOT EXISTS idx_llamadas_sentido
    ON llamadas (sentido);

CREATE INDEX IF NOT EXISTS idx_llamadas_archivo
    ON llamadas (archivo_origen);

CREATE INDEX IF NOT EXISTS idx_etl_cargas_iniciado
    ON etl_cargas (iniciado_en DESC);
