"""Acceso a PostgreSQL: conexión, transacciones y cursor."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

import psycopg2
from psycopg2.extensions import connection as ConexionPG
from psycopg2.extensions import cursor as CursorPG
from psycopg2.extras import RealDictCursor

from config.settings import obtener_settings

logger = logging.getLogger(__name__)


@contextmanager
def conexion() -> Iterator[ConexionPG]:
    """Abre una conexión, confirma al salir y revierte si hay excepción."""
    ajustes = obtener_settings()
    conn = psycopg2.connect(**ajustes.dsn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def cursor(como_diccionario: bool = False) -> Iterator[CursorPG]:
    """Cursor dentro de una transacción gestionada."""
    fabrica = RealDictCursor if como_diccionario else None
    with conexion() as conn:
        with conn.cursor(cursor_factory=fabrica) as cur:
            yield cur


def verificar_conexion() -> bool:
    """Comprueba que la base de datos responde."""
    try:
        with cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except Exception as exc:  # pragma: no cover - depende del entorno
        logger.warning("No se pudo conectar a PostgreSQL: %s", exc)
        return False
