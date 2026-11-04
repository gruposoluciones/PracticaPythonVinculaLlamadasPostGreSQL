"""Tareas de mantenimiento sobre datos ya cargados."""
from __future__ import annotations

import argparse
import logging

from psycopg2.extras import execute_batch

from cargadatos import normalizacion as norm
from cargadatos.db import conexion
from config.settings import obtener_settings

logger = logging.getLogger(__name__)


def reclasificar_numeros() -> dict[str, int]:
    """Recalcula ``titular_clase``, ``origen_clase`` y ``destino_clase``.

    Útil después de actualizar las reglas de clasificación o de cargar datos
    con una versión anterior del ETL.
    """
    ajustes = obtener_settings()
    with conexion() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, titular, origen, destino FROM llamadas")
            filas = cur.fetchall()
            datos = [
                (
                    norm.clasificar_telefono(titular, ajustes.pais_codigo),
                    norm.clasificar_telefono(origen, ajustes.pais_codigo),
                    norm.clasificar_telefono(destino, ajustes.pais_codigo),
                    identificador,
                )
                for identificador, titular, origen, destino in filas
            ]
            if datos:
                execute_batch(
                    cur,
                    """
                    UPDATE llamadas
                       SET titular_clase = %s,
                           origen_clase = %s,
                           destino_clase = %s
                     WHERE id = %s
                    """,
                    datos,
                    page_size=1000,
                )
    return {"actualizados": len(datos) if datos else 0}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Recalcula la clasificación de números (móvil/fijo/extranjero)."
    )
    parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
    resultado = reclasificar_numeros()
    print(f"Filas reclasificadas: {resultado['actualizados']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
