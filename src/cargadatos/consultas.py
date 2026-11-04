"""Consultas de negocio sobre la tabla ``llamadas``.

Todas las funciones reciben valores ya validados y usan parámetros ``%s``:
nunca se concatena entrada del usuario en el SQL.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from cargadatos.db import cursor
from config.settings import obtener_settings

MAX_TAMANO_PAGINA = 500


def _solo_digitos(valor: str | None) -> str:
    return re.sub(r"\D", "", valor or "")


def _fecha(valor: str | date | None) -> date | None:
    if valor is None or valor == "":
        return None
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor))


def construir_filtros(
    numero: str | None = None,
    desde: str | date | None = None,
    hasta: str | date | None = None,
    tipo: str | None = None,
    sentido: str | None = None,
    parcial: bool = False,
) -> tuple[str, list[Any]]:
    """Devuelve (cláusula WHERE, parámetros) para los filtros indicados."""
    condiciones: list[str] = []
    parametros: list[Any] = []

    if numero:
        digitos = _solo_digitos(numero)
        if not digitos:
            raise ValueError("El número debe contener al menos un dígito.")
        if parcial:
            patron = f"%{digitos}%"
            condiciones.append(
                "(titular LIKE %s OR origen LIKE %s OR destino LIKE %s)"
            )
            parametros.extend([patron, patron, patron])
        else:
            condiciones.append(
                "(titular = %s OR origen = %s OR destino = %s)"
            )
            parametros.extend([digitos, digitos, digitos])

    fecha_desde = _fecha(desde)
    if fecha_desde:
        condiciones.append("fecha >= %s")
        parametros.append(fecha_desde)

    fecha_hasta = _fecha(hasta)
    if fecha_hasta:
        condiciones.append("fecha <= %s")
        parametros.append(fecha_hasta)

    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        raise ValueError("La fecha 'desde' no puede ser posterior a 'hasta'.")

    if tipo:
        condiciones.append("tipo = %s")
        parametros.append(tipo)

    if sentido:
        condiciones.append("sentido = %s")
        parametros.append(sentido)

    return (" AND ".join(condiciones) if condiciones else "TRUE"), parametros


def _limites(pagina: int, tamano: int) -> tuple[int, int]:
    maximo = obtener_settings().max_filas
    tamano = max(1, min(int(tamano), maximo, MAX_TAMANO_PAGINA))
    pagina = max(1, int(pagina))
    return tamano, (pagina - 1) * tamano


def listar_llamadas(
    numero: str | None = None,
    desde: str | date | None = None,
    hasta: str | date | None = None,
    tipo: str | None = None,
    sentido: str | None = None,
    parcial: bool = False,
    pagina: int = 1,
    tamano: int = 50,
) -> dict[str, Any]:
    """Listado paginado de comunicaciones filtradas."""
    where, parametros = construir_filtros(numero, desde, hasta, tipo, sentido, parcial)
    limite, desplazamiento = _limites(pagina, tamano)

    with cursor(como_diccionario=True) as cur:
        cur.execute(f"SELECT count(*) AS total FROM llamadas WHERE {where}", parametros)
        total = int(cur.fetchone()["total"])

        cur.execute(
            f"""
            SELECT id, titular, destino, origen, fecha, hora, duracion_seg,
                   tipo, sentido, archivo_origen, fila_origen
              FROM llamadas
             WHERE {where}
             ORDER BY fecha DESC NULLS LAST, hora DESC NULLS LAST, id DESC
             LIMIT %s OFFSET %s
            """,
            [*parametros, limite, desplazamiento],
        )
        filas = cur.fetchall()

    return {
        "total": total,
        "pagina": pagina,
        "tamano": limite,
        "paginas": (total + limite - 1) // limite if total else 0,
        "filas": filas,
    }


def obtener_resumen() -> dict[str, Any]:
    """Indicadores globales de la base de datos."""
    with cursor(como_diccionario=True) as cur:
        cur.execute(
            """
            SELECT count(*)                                    AS total,
                   count(*) FILTER (WHERE origen IS NULL)      AS sin_origen,
                   count(*) FILTER (WHERE origen IS NOT NULL)  AS con_origen,
                   count(DISTINCT titular)                     AS lineas,
                   count(DISTINCT archivo_origen)              AS archivos,
                   min(fecha)                                  AS primera_fecha,
                   max(fecha)                                  AS ultima_fecha,
                   coalesce(sum(duracion_seg), 0)              AS duracion_total
              FROM llamadas
            """
        )
        resumen = dict(cur.fetchone())

        cur.execute(
            """
            SELECT id, archivo, formato, filas_leidas, filas_insertadas,
                   filas_rechazadas, estado, iniciado_en
              FROM etl_cargas
             ORDER BY id DESC
             LIMIT 1
            """
        )
        ultima = cur.fetchone()
        resumen["ultima_carga"] = dict(ultima) if ultima else None

    resumen["duracion_total"] = int(resumen["duracion_total"] or 0)
    return resumen


def estadisticas(
    numero: str | None = None,
    desde: str | date | None = None,
    hasta: str | date | None = None,
    tipo: str | None = None,
    sentido: str | None = None,
    parcial: bool = False,
) -> dict[str, Any]:
    """Totales y promedios para el conjunto filtrado."""
    where, parametros = construir_filtros(numero, desde, hasta, tipo, sentido, parcial)
    with cursor(como_diccionario=True) as cur:
        cur.execute(
            f"""
            SELECT count(*)                                              AS total,
                   coalesce(sum(duracion_seg), 0)                        AS duracion_total,
                   coalesce(round(avg(duracion_seg))::int, 0)            AS duracion_promedio,
                   count(*) FILTER (WHERE tipo = 'Voz')                  AS voz,
                   count(*) FILTER (WHERE tipo = 'SMS')                  AS sms,
                   count(*) FILTER (WHERE sentido = 'Entrante')          AS entrantes,
                   count(*) FILTER (WHERE sentido = 'Saliente')          AS salientes,
                   count(DISTINCT fecha)                                 AS dias,
                   count(DISTINCT titular)                               AS lineas,
                   min(fecha)                                            AS primera_fecha,
                   max(fecha)                                            AS ultima_fecha
              FROM llamadas
             WHERE {where}
            """,
            parametros,
        )
        datos = dict(cur.fetchone())
    datos["duracion_total"] = int(datos["duracion_total"] or 0)
    return datos


def agregados(
    por: str = "dia",
    numero: str | None = None,
    desde: str | date | None = None,
    hasta: str | date | None = None,
    tipo: str | None = None,
    sentido: str | None = None,
    parcial: bool = False,
    limite: int = 20,
) -> list[dict[str, Any]]:
    """Agrupaciones: ``dia``, ``destino``, ``origen``, ``tipo`` o ``sentido``."""
    where, parametros = construir_filtros(numero, desde, hasta, tipo, sentido, parcial)
    limite = max(1, min(int(limite), 100))

    if por == "dia":
        consulta = f"""
            SELECT fecha AS clave,
                   count(*) AS total,
                   coalesce(sum(duracion_seg), 0) AS duracion
              FROM llamadas
             WHERE {where} AND fecha IS NOT NULL
             GROUP BY fecha
             ORDER BY fecha
        """
        parametros_consulta = parametros
    elif por in {"destino", "origen"}:
        consulta = f"""
            SELECT {por} AS clave,
                   count(*) AS total,
                   coalesce(sum(duracion_seg), 0) AS duracion
              FROM llamadas
             WHERE {where} AND {por} IS NOT NULL
             GROUP BY {por}
             ORDER BY total DESC
             LIMIT %s
        """
        parametros_consulta = [*parametros, limite]
    elif por in {"tipo", "sentido"}:
        consulta = f"""
            SELECT {por} AS clave,
                   count(*) AS total,
                   coalesce(sum(duracion_seg), 0) AS duracion
              FROM llamadas
             WHERE {where} AND {por} IS NOT NULL
             GROUP BY {por}
             ORDER BY total DESC
        """
        parametros_consulta = parametros
    else:
        raise ValueError("Agrupación no válida. Use: dia, destino, origen, tipo o sentido.")

    with cursor(como_diccionario=True) as cur:
        cur.execute(consulta, parametros_consulta)
        return [dict(fila) for fila in cur.fetchall()]


def _where_vinculacion() -> str:
    return (
        "((titular = %s AND (origen = %s OR destino = %s)) "
        " OR (titular = %s AND (origen = %s OR destino = %s)))"
    )


def vincular(
    numero_a: str,
    numero_b: str,
    pagina: int = 1,
    tamano: int = 50,
) -> dict[str, Any]:
    """Comunicaciones entre dos líneas, en cualquier sentido."""
    a = _solo_digitos(numero_a)
    b = _solo_digitos(numero_b)
    if not a or not b:
        raise ValueError("Ambos números son obligatorios.")
    if a == b:
        raise ValueError("Los números A y B deben ser distintos.")

    where = _where_vinculacion()
    parametros = [a, b, b, b, a, a]
    limite, desplazamiento = _limites(pagina, tamano)

    with cursor(como_diccionario=True) as cur:
        cur.execute(
            f"""
            SELECT count(*)                                        AS total,
                   count(*) FILTER (WHERE titular = %s)            AS titular_a,
                   count(*) FILTER (WHERE titular = %s)            AS titular_b,
                   count(*) FILTER (WHERE sentido = 'Entrante')    AS entrantes,
                   count(*) FILTER (WHERE sentido = 'Saliente')    AS salientes,
                   coalesce(sum(duracion_seg), 0)                  AS duracion_total,
                   coalesce(round(avg(duracion_seg))::int, 0)      AS duracion_promedio,
                   count(DISTINCT fecha)                           AS dias,
                   min(fecha)                                      AS primera_fecha,
                   max(fecha)                                      AS ultima_fecha
              FROM llamadas
             WHERE {where}
            """,
            [a, b, *parametros],
        )
        resumen = dict(cur.fetchone())

        cur.execute(
            f"""
            SELECT id, titular, destino, origen, fecha, hora, duracion_seg,
                   tipo, sentido, archivo_origen, fila_origen
              FROM llamadas
             WHERE {where}
             ORDER BY fecha DESC NULLS LAST, hora DESC NULLS LAST, id DESC
             LIMIT %s OFFSET %s
            """,
            [*parametros, limite, desplazamiento],
        )
        filas = cur.fetchall()

    total = int(resumen["total"])
    resumen["duracion_total"] = int(resumen["duracion_total"] or 0)
    return {
        "numero_a": a,
        "numero_b": b,
        "resumen": resumen,
        "total": total,
        "pagina": pagina,
        "tamano": limite,
        "paginas": (total + limite - 1) // limite if total else 0,
        "filas": filas,
    }


def exportar_filas(
    numero: str | None = None,
    desde: str | date | None = None,
    hasta: str | date | None = None,
    tipo: str | None = None,
    sentido: str | None = None,
    parcial: bool = False,
    limite: int = 20_000,
) -> list[dict[str, Any]]:
    """Filas filtradas para exportación CSV, con un tope duro."""
    where, parametros = construir_filtros(numero, desde, hasta, tipo, sentido, parcial)
    limite = max(1, min(int(limite), 50_000))
    with cursor(como_diccionario=True) as cur:
        cur.execute(
            f"""
            SELECT titular, destino, origen, fecha, hora, duracion_seg,
                   tipo, sentido, archivo_origen
              FROM llamadas
             WHERE {where}
             ORDER BY fecha DESC NULLS LAST, hora DESC NULLS LAST, id DESC
             LIMIT %s
            """,
            [*parametros, limite],
        )
        return [dict(fila) for fila in cur.fetchall()]


def listar_cargas(limite: int = 20) -> list[dict[str, Any]]:
    """Historial de cargas para la pestaña de administración."""
    with cursor(como_diccionario=True) as cur:
        cur.execute(
            """
            SELECT id, archivo, formato, hash_sha256, filas_leidas,
                   filas_insertadas, filas_rechazadas, estado,
                   mensaje_error, iniciado_en, finalizado_en
              FROM etl_cargas
             ORDER BY id DESC
             LIMIT %s
            """,
            (max(1, min(int(limite), 100)),),
        )
        return [dict(fila) for fila in cur.fetchall()]
