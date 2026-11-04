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
