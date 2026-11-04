"""ETL: carga de Excel/CSV a PostgreSQL con trazabilidad e idempotencia."""
from __future__ import annotations

import argparse
import hashlib
import logging
import shutil
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from psycopg2.extras import execute_values

from cargadatos import normalizacion as norm
from cargadatos.db import conexion
from cargadatos.excel_reader import leer_archivo

logger = logging.getLogger(__name__)

SQL_INSERTAR = """
    INSERT INTO llamadas (
        carga_id, titular, destino, origen, fecha, hora,
        duracion_seg, tipo, sentido, archivo_origen, fila_origen, hash_fila
    )
    VALUES %s
    ON CONFLICT (hash_fila) DO NOTHING
    RETURNING id
"""

PLANTILLA_INSERTAR = (
    "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)


@dataclass
class ResultadoCarga:
    """Resumen de una carga, apto para CLI y para la API."""

    archivo: str
    formato: str
    filas_leidas: int
    filas_insertadas: int
    filas_duplicadas: int
    filas_rechazadas: int
    motivos: list[str] = field(default_factory=list)
    segundos: float = 0.0
    carga_id: int | None = None

    def como_dict(self) -> dict[str, object]:
        return asdict(self)


def hash_archivo(ruta: Path) -> str:
    """SHA-256 del archivo para trazabilidad."""
    digest = hashlib.sha256()
    with ruta.open("rb") as manejador:
        for bloque in iter(lambda: manejador.read(1024 * 1024), b""):
            digest.update(bloque)
    return digest.hexdigest()


def _normalizar_fila(registro: dict[str, str]) -> tuple[dict[str, object] | None, str | None]:
    """Normaliza una fila cruda. Devuelve (registro, motivo_de_rechazo)."""
    titular = norm.normalizar_telefono(registro.get("titular"))
    if not titular:
        return None, "titular ausente o inválido"

    origen = None
    if registro.get("origen"):
        origen = norm.normalizar_telefono(registro["origen"])
        if not origen:
            return None, "origen inválido"

    destino = None
    if registro.get("destino"):
        destino = norm.normalizar_telefono(registro["destino"])
        if not destino:
            return None, "destino inválido"

    fecha = norm.normalizar_fecha(registro.get("fecha")) or norm.normalizar_fecha(
        registro.get("fecha_alterna")
    )
    if not fecha:
        return None, "fecha ausente o inválida"

    hora = norm.normalizar_hora(registro.get("hora")) or norm.normalizar_hora(
        registro.get("hora_alterna")
    )
    if not hora:
        return None, "hora ausente o inválida"

    duracion = norm.normalizar_duracion(registro.get("duracion"))
    if duracion is None:
        return None, "duración inválida"

    tipo = norm.normalizar_tipo(registro.get("tipo"))
    sentido = norm.normalizar_sentido(registro.get("sentido"))

    hash_fila = norm.calcular_hash_fila(
        titular, origen, destino, fecha, hora, duracion, tipo, sentido
    )

    return (
        {
            "titular": titular,
            "destino": destino,
            "origen": origen,
            "fecha": fecha,
            "hora": hora,
            "duracion_seg": duracion,
            "tipo": tipo,
            "sentido": sentido,
            "fila_origen": int(registro.get("fila_origen") or 0),
            "hash_fila": hash_fila,
        },
        None,
    )


def _marcar_error(carga_id: int | None, mensaje: str) -> None:
    if not carga_id:
        return
    try:
        with conexion() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE etl_cargas
                       SET estado = 'error',
                           mensaje_error = %s,
                           finalizado_en = now()
                     WHERE id = %s
                    """,
                    (mensaje[:2000], carga_id),
                )
    except Exception:  # pragma: no cover - la base ya no responde
        logger.exception("No se pudo registrar el error de la carga %s", carga_id)


def _mover_a_procesados(ruta: Path) -> Path:
    from config.settings import obtener_settings

    destino_dir = obtener_settings().directorio_procesados
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / ruta.name
    if destino.exists():
        marca = datetime.now().strftime("%Y%m%d%H%M%S")
        destino = destino_dir / f"{ruta.stem}_{marca}{ruta.suffix}"
    shutil.move(str(ruta), str(destino))
    return destino


def cargar_archivo(
    ruta: str | Path,
    mover: bool = False,
    nombre_original: str | None = None,
) -> ResultadoCarga:
    """Carga un archivo completo y devuelve el resumen de la operación.

    Cada lote de inserción se ejecuta en una transacción. Los errores de una
    fila no abortan la carga: se cuentan y se informan en ``motivos``.
    """
    ruta = Path(ruta)
    nombre = nombre_original or ruta.name
    inicio = time.monotonic()
    sha = hash_archivo(ruta)
    carga_id: int | None = None

    try:
        with conexion() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO etl_cargas (archivo, hash_sha256, formato, estado)
                    VALUES (%s, %s, 'pendiente', 'en_proceso')
                    RETURNING id
                    """,
                    (nombre, sha),
                )
                carga_id = int(cur.fetchone()[0])

        tabla = leer_archivo(ruta)

        validos: list[tuple[object, ...]] = []
        motivos: list[str] = []
        for registro in tabla.filas:
            normalizado, motivo = _normalizar_fila(registro)
            if normalizado is None:
                if len(motivos) < 50:
                    motivos.append(
                        f"fila {registro.get('fila_origen')}: {motivo}"
                    )
                continue
            validos.append(
                (
                    carga_id,
                    normalizado["titular"],
                    normalizado["destino"],
                    normalizado["origen"],
                    normalizado["fecha"],
                    normalizado["hora"],
                    normalizado["duracion_seg"],
                    normalizado["tipo"],
                    normalizado["sentido"],
                    nombre,
                    normalizado["fila_origen"],
                    normalizado["hash_fila"],
                )
            )

        insertadas = 0
        with conexion() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE etl_cargas SET formato = %s WHERE id = %s",
                    (tabla.formato, carga_id),
                )
                if validos:
                    devueltas = execute_values(
                        cur,
                        SQL_INSERTAR,
                        validos,
                        template=PLANTILLA_INSERTAR,
                        page_size=500,
                        fetch=True,
                    )
                    insertadas = len(devueltas)

                rechazadas = tabla.total_filas - len(validos)
                cur.execute(
                    """
                    UPDATE etl_cargas
                       SET filas_leidas = %s,
                           filas_insertadas = %s,
                           filas_rechazadas = %s,
                           estado = 'ok',
                           finalizado_en = now()
                     WHERE id = %s
                    """,
                    (tabla.total_filas, insertadas, rechazadas, carga_id),
                )

        if mover:
            _mover_a_procesados(ruta)

        resultado = ResultadoCarga(
            archivo=nombre,
            formato=tabla.formato,
            filas_leidas=tabla.total_filas,
            filas_insertadas=insertadas,
            filas_duplicadas=len(validos) - insertadas,
            filas_rechazadas=tabla.total_filas - len(validos),
            motivos=motivos,
            segundos=round(time.monotonic() - inicio, 3),
            carga_id=carga_id,
        )
        logger.info(
            "Carga %s: %s leídas, %s insertadas, %s duplicadas, %s rechazadas (%.2fs)",
            nombre,
            resultado.filas_leidas,
            resultado.filas_insertadas,
            resultado.filas_duplicadas,
            resultado.filas_rechazadas,
            resultado.segundos,
        )
        return resultado

    except Exception as exc:
        logger.exception("Error al cargar %s", nombre)
        _marcar_error(carga_id, str(exc))
        raise


def _configurar_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Carga archivos Excel/CSV de llamadas en PostgreSQL."
    )
    parser.add_argument("archivos", nargs="+", help="Ruta(s) de los archivos a cargar")
    parser.add_argument(
        "--mover",
        action="store_true",
        help="Mover el archivo a data/procesados tras una carga correcta",
    )
    parser.add_argument("--verbose", action="store_true", help="Mostrar detalle de depuración")
    args = parser.parse_args(argv)

    _configurar_logging(args.verbose)
    fallos = 0
    for nombre in args.archivos:
        print(f"\n=== Cargando {nombre} ===")
        try:
            resultado = cargar_archivo(nombre, mover=args.mover)
        except Exception as exc:
            fallos += 1
            print(f"ERROR: {exc}", file=sys.stderr)
            continue
        print(f"Formato detectado : {resultado.formato}")
        print(f"Filas leídas      : {resultado.filas_leidas}")
        print(f"Filas insertadas  : {resultado.filas_insertadas}")
        print(f"Duplicadas        : {resultado.filas_duplicadas}")
        print(f"Rechazadas        : {resultado.filas_rechazadas}")
        for motivo in resultado.motivos[:10]:
            print(f"  - {motivo}")
        print(f"Tiempo            : {resultado.segundos}s")

    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
