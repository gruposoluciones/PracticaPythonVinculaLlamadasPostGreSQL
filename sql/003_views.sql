-- Vistas de apoyo para consultas.

CREATE OR REPLACE VIEW v_vinculaciones AS
SELECT id,
       titular,
       origen,
       destino,
       fecha,
       hora,
       duracion_seg,
       tipo,
       sentido,
       archivo_origen
  FROM llamadas
 WHERE origen IS NOT NULL;

CREATE OR REPLACE VIEW v_resumen_diario AS
SELECT fecha,
       count(*)                       AS total,
       coalesce(sum(duracion_seg), 0) AS duracion_total,
       count(*) FILTER (WHERE tipo = 'Voz')     AS voz,
       count(*) FILTER (WHERE tipo = 'SMS')     AS sms,
       count(*) FILTER (WHERE sentido = 'Entrante') AS entrantes,
       count(*) FILTER (WHERE sentido = 'Saliente') AS salientes
  FROM llamadas
 WHERE fecha IS NOT NULL
 GROUP BY fecha;

-- Relación agregada número <-> IMEI.
CREATE OR REPLACE VIEW v_vinculaciones_imei AS
SELECT titular                          AS numero,
       imei,
       count(*)                         AS registros,
       min(fecha)                       AS primera_fecha,
       max(fecha)                       AS ultima_fecha,
       count(DISTINCT fecha)            AS dias,
       string_agg(DISTINCT operador, ', ' ORDER BY operador)      AS operadores,
       string_agg(DISTINCT archivo_origen, ', ' ORDER BY archivo_origen) AS archivos
  FROM llamadas
 WHERE imei IS NOT NULL
   AND imei <> ''
   AND titular IS NOT NULL
 GROUP BY titular, imei;

COMMENT ON VIEW v_vinculaciones_imei IS
    'Pares número-IMEI con conteo de registros y fechas.';

