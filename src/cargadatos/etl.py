"""ETL: carga de CDR (Excel/CSV) a PostgreSQL con detección de columnas.

Los campos opcionales ausentes se guardan como ``NULL``. Solo se rechaza una
fila cuando no contiene ningún número telefónico utilizable.
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import shutil
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time as time_type
from pathlib import Path

from psycopg2.extras import execute_values

from cargadatos import mapeo as deteccion_mapeo
from cargadatos import normalizacion as norm
from cargadatos.db import conexion
from cargadatos.excel_reader import leer_archivo

logger = logging.getLogger(__name__)

SQL_INSERTAR = """
    INSERT INTO llamadas (
        carga_id, titular, destino, origen, fecha, hora,
        duracion_seg, tipo, sentido,
        imei, imsi, celda, lac, antena, latitud, longitud,
        operador, tecnologia, roaming,
        titular_clase, origen_clase, destino_clase,
        archivo_origen, fila_origen, hash_fila
    )
    VALUES %s
    ON CONFLICT (hash_fila) DO NOTHING
    RETURNING id
"""

PLANTILLA_INSERTAR = "(" + ", ".join(["%s"] * 25) + ")"


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
    mapeo: dict[str, int] = field(default_factory=dict)
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


def _entero(valor: object, minimo: int, maximo: int) -> int | None:
    crudo = norm.texto(valor)
    if not crudo:
        return None
    try:
        numero = int(float(crudo.replace(",", ".")))
    except ValueError:
        return None
    return numero if minimo <= numero <= maximo else None


def _fecha_por_componentes(registro: dict[str, str]) -> date | None:
    anio = _entero(registro.get("anio"), 1900, 2100)
    mes = _entero(registro.get("mes"), 1, 12)
    dia = _entero(registro.get("dia"), 1, 31)
    if not (anio and mes and dia):
        return None
    try:
        return date(anio, mes, dia)
    except ValueError:
        return None


def _hora_por_componentes(registro: dict[str, str]) -> time_type | None:
    hora = _entero(registro.get("hora_num"), 0, 23)
    minuto = _entero(registro.get("minuto"), 0, 59)
    segundo = _entero(registro.get("segundo"), 0, 59)
    if hora is None:
        return None
    return time_type(hora, minuto or 0, segundo or 0)


def normalizar_registro(
    registro: dict[str, str],
    codigo_pais: str = "51",
) -> tuple[dict[str, object] | None, str | None]:
    """Normaliza una fila cruda. Devuelve ``(registro, motivo_de_rechazo)``."""
    fecha = norm.normalizar_fecha(registro.get("fecha"))
    hora = norm.normalizar_hora(registro.get("hora"))

    combinada = registro.get("fecha_hora")
    if combinada:
        fecha = fecha or norm.normalizar_fecha(combinada)
        hora = hora or norm.normalizar_hora(combinada)

    fecha = fecha or norm.normalizar_fecha(registro.get("fecha_alterna"))
    hora = hora or norm.normalizar_hora(registro.get("hora_alterna"))
    fecha = fecha or _fecha_por_componentes(registro)
    hora = hora or _hora_por_componentes(registro)

    origen = norm.normalizar_telefono(registro.get("origen"))
    destino = norm.normalizar_telefono(registro.get("destino"))
    titular = (
        norm.normalizar_telefono(registro.get("titular"))
        or origen
        or destino
    )
    if not titular:
        return None, "sin número titular, origen ni destino"

    sentido = norm.normalizar_sentido(registro.get("sentido"))
    if not sentido and origen and destino:
        if origen == titular and destino != titular:
            sentido = "Saliente"
        elif destino == titular and origen != titular:
            sentido = "Entrante"

    duracion = norm.normalizar_duracion(registro.get("duracion"))
    tipo = norm.normalizar_tipo(registro.get("tipo"))

    imei = norm.normalizar_imei(registro.get("imei"))
    imsi = norm.normalizar_imsi(registro.get("imsi"))
    celda = norm.normalizar_identificador(registro.get("celda"))
    lac = norm.normalizar_identificador(registro.get("lac"))
    antena = norm.normalizar_identificador(registro.get("antena"))
    latitud = norm.normalizar_coordenada(registro.get("latitud"), 90)
    longitud = norm.normalizar_coordenada(registro.get("longitud"), 180)
    operador = norm.normalizar_identificador(registro.get("operador"))
    tecnologia = norm.normalizar_identificador(registro.get("tecnologia"))
    roaming = norm.normalizar_booleano(registro.get("roaming"))

    hash_fila = norm.calcular_hash_fila(
        titular,
        origen,
        destino,
        fecha,
        hora,
        duracion,
        tipo,
        sentido,
        imei=imei,
        celda=celda,
        antena=antena,
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
            "imei": imei,
            "imsi": imsi,
            "celda": celda,
            "lac": lac,
            "antena": antena,
            "latitud": latitud,
            "longitud": longitud,
            "operador": operador,
            "tecnologia": tecnologia,
            "roaming": roaming,
            "titular_clase": norm.clasificar_telefono(titular, codigo_pais),
            "origen_clase": norm.clasificar_telefono(origen, codigo_pais),
            "destino_clase": norm.clasificar_telefono(destino, codigo_pais),
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
    mapeo_forzado: dict[str, int] | None = None,
) -> ResultadoCarga:
    """Carga un archivo completo y devuelve el resumen de la operación."""
    from config.settings import obtener_settings

    ruta = Path(ruta)
    nombre = nombre_original or ruta.name
    inicio = time.monotonic()
    sha = hash_archivo(ruta)
    ajustes = obtener_settings()
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

        tabla = leer_archivo(ruta, mapeo_forzado=mapeo_forzado)

        validos: list[tuple[object, ...]] = []
        motivos: list[str] = []
        for registro in tabla.filas:
            normalizado, motivo = normalizar_registro(
                registro, codigo_pais=ajustes.pais_codigo
            )
            if normalizado is None:
                if len(motivos) < 50:
                    motivos.append(f"fila {registro.get('fila_origen')}: {motivo}")
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
                    normalizado["imei"],
                    normalizado["imsi"],
                    normalizado["celda"],
                    normalizado["lac"],
                    normalizado["antena"],
                    normalizado["latitud"],
                    normalizado["longitud"],
                    normalizado["operador"],
                    normalizado["tecnologia"],
                    normalizado["roaming"],
                    normalizado["titular_clase"],
                    normalizado["origen_clase"],
                    normalizado["destino_clase"],
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
            mapeo=tabla.mapeo,
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
        description="Carga archivos CDR (Excel/CSV) en PostgreSQL."
    )
    parser.add_argument("archivos", nargs="+", help="Ruta(s) de los archivos a cargar")
    parser.add_argument(
        "--mover",
        action="store_true",
        help="Mover el archivo a data/procesados tras una carga correcta",
    )
    parser.add_argument(
        "--mapeo",
        help=(
            "Forzar columnas: 'titular=0,origen=3,destino=1,fecha=4,hora=13,"
            "duracion=14,tipo=15,sentido=16,imei=17,celda=18'"
        ),
    )
    parser.add_argument("--verbose", action="store_true", help="Mostrar detalle de depuración")
    args = parser.parse_args(argv)

    _configurar_logging(args.verbose)
    mapeo_forzado = deteccion_mapeo.parsear_mapeo(args.mapeo) if args.mapeo else None

    fallos = 0
    for nombre in args.archivos:
        print(f"\n=== Cargando {nombre} ===")
        try:
            resultado = cargar_archivo(
                nombre, mover=args.mover, mapeo_forzado=mapeo_forzado
            )
        except Exception as exc:
            fallos += 1
            print(f"ERROR: {exc}", file=sys.stderr)
            continue
        print(f"Formato detectado : {resultado.formato}")
        print(f"Columnas          : {resultado.mapeo}")
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
