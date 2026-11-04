"""API local (FastAPI) y servidor del frontend HTML."""
from __future__ import annotations

import csv
import io
import logging
import tempfile
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import psycopg2
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from cargadatos import consultas
from cargadatos.db import verificar_conexion
from cargadatos.etl import cargar_archivo
from cargadatos.excel_reader import FormatoNoSoportado, es_archivo_soportado
from cargadatos.mapeo import parsear_mapeo
from config.settings import ConfiguracionInvalida, RAIZ, obtener_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(
            RAIZ / "app.log",
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Carga de datos de llamadas",
    description="Carga Excel/CSV en PostgreSQL y consulta los registros.",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)


@app.middleware("http")
async def cabeceras_de_seguridad(request, call_next):
    respuesta = await call_next(request)
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    respuesta.headers["X-Frame-Options"] = "DENY"
    respuesta.headers["Referrer-Policy"] = "no-referrer"
    respuesta.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self'; script-src 'self'; "
        "img-src 'self' data:; connect-src 'self'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'none'"
    )
    if request.url.path.startswith("/api/"):
        respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


@app.exception_handler(ConfiguracionInvalida)
async def manejar_configuracion(request, exc: ConfiguracionInvalida):
    logger.error("Configuración inválida: %s", exc)
    return Response(
        content='{"detalle":"Configuración de base de datos incompleta."}',
        status_code=503,
        media_type="application/json",
    )


@app.exception_handler(psycopg2.Error)
async def manejar_error_bd(request, exc: psycopg2.Error):
    logger.error("Error de PostgreSQL: %s", exc)
    return Response(
        content='{"detalle":"No se pudo consultar la base de datos."}',
        status_code=503,
        media_type="application/json",
    )


def _entero(valor: int, minimo: int, maximo: int) -> int:
    return max(minimo, min(int(valor), maximo))


@app.get("/health")
@app.get("/api/salud")
def salud() -> dict[str, Any]:
    conectada = verificar_conexion()
    return {"estado": "ok" if conectada else "sin_base_de_datos", "base_de_datos": conectada}


@app.get("/api/resumen")
def resumen() -> dict[str, Any]:
    return consultas.obtener_resumen()


@app.get("/api/llamadas")
def llamadas(
    numero: str | None = Query(None, max_length=20),
    desde: str | None = Query(None, max_length=10),
    hasta: str | None = Query(None, max_length=10),
    tipo: str | None = Query(None, max_length=20),
    sentido: str | None = Query(None, max_length=20),
    parcial: bool = False,
    pagina: int = Query(1, ge=1),
    tamano: int = Query(50, ge=1, le=500),
) -> dict[str, Any]:
    try:
        return consultas.listar_llamadas(
            numero, desde, hasta, tipo, sentido, parcial, pagina, tamano
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/vinculaciones")
def vinculaciones(
    numeros: str | None = Query(
        None,
        max_length=250,
        description="De 2 a 10 números separados por coma.",
    ),
    a: str | None = Query(None, max_length=20),
    b: str | None = Query(None, max_length=20),
    pagina: int = Query(1, ge=1),
    tamano: int = Query(50, ge=1, le=500),
) -> dict[str, Any]:
    seleccion = numeros or ",".join(valor for valor in (a, b) if valor)
    if not seleccion:
        raise HTTPException(
            status_code=400,
            detail="Indica 'numeros' (2 a 10) o los parámetros 'a' y 'b'.",
        )
    try:
        return consultas.vincular_varios(seleccion, pagina, tamano)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/imei/numero")
def imei_por_numero(
    numero: str = Query(..., min_length=8, max_length=20),
) -> dict[str, Any]:
    """IMEIs registrados para un número de celular."""
    try:
        return consultas.vincular_imei_por_numero(numero)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/imei/equipo")
def numeros_por_imei(
    imei: str = Query(..., min_length=14, max_length=20),
) -> dict[str, Any]:
    """Números asociados a un IMEI."""
    try:
        return consultas.vincular_numero_por_imei(imei)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/imei/pares")
def pares_imei(
    pagina: int = Query(1, ge=1),
    tamano: int = Query(50, ge=1, le=500),
) -> dict[str, Any]:
    """Listado paginado de pares número-IMEI."""
    return consultas.listar_pares_imei(pagina, tamano)


@app.get("/api/estadisticas")
def estadisticas(
    numero: str | None = Query(None, max_length=20),
    desde: str | None = Query(None, max_length=10),
    hasta: str | None = Query(None, max_length=10),
    tipo: str | None = Query(None, max_length=20),
    sentido: str | None = Query(None, max_length=20),
    parcial: bool = False,
) -> dict[str, Any]:
    try:
        return consultas.estadisticas(numero, desde, hasta, tipo, sentido, parcial)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/agregados")
def agregados(
    por: str = Query("dia"),
    numero: str | None = Query(None, max_length=20),
    desde: str | None = Query(None, max_length=10),
    hasta: str | None = Query(None, max_length=10),
    tipo: str | None = Query(None, max_length=20),
    sentido: str | None = Query(None, max_length=20),
    parcial: bool = False,
    limite: int = Query(20, ge=1, le=100),
) -> list[dict[str, Any]]:
    try:
        return consultas.agregados(
            por, numero, desde, hasta, tipo, sentido, parcial, limite
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/cargas")
def cargas(limite: int = Query(20, ge=1, le=100)) -> list[dict[str, Any]]:
    return consultas.listar_cargas(limite)


@app.post("/api/cargar")
def cargar(
    archivo: UploadFile = File(...),
    mapeo: str | None = Form(None),
) -> dict[str, Any]:
    ajustes = obtener_settings()
    nombre = Path(archivo.filename or "").name
    if not nombre or not es_archivo_soportado(nombre):
        raise HTTPException(
            status_code=400,
            detail="Formato no soportado. Use .xlsx, .xls o .csv.",
        )

    mapeo_forzado = None
    if mapeo:
        try:
            mapeo_forzado = parsear_mapeo(mapeo)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    limite_bytes = ajustes.max_subida_mb * 1024 * 1024
    contenido = archivo.file.read(limite_bytes + 1)
    if len(contenido) > limite_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"El archivo supera el máximo de {ajustes.max_subida_mb} MB.",
        )
    if not contenido:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")

    sufijo = Path(nombre).suffix.lower()
    descriptor, ruta_temporal = tempfile.mkstemp(suffix=sufijo, prefix="carga_")
    ruta = Path(ruta_temporal)
    try:
        with open(descriptor, "wb") as manejador:
            manejador.write(contenido)
        resultado = cargar_archivo(
            ruta,
            mover=False,
            nombre_original=nombre,
            mapeo_forzado=mapeo_forzado,
        )
        return resultado.como_dict()
    except FormatoNoSoportado as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        ruta.unlink(missing_ok=True)


@app.get("/api/exportar.csv")
def exportar(
    numero: str | None = Query(None, max_length=20),
    desde: str | None = Query(None, max_length=10),
    hasta: str | None = Query(None, max_length=10),
    tipo: str | None = Query(None, max_length=20),
    sentido: str | None = Query(None, max_length=20),
    parcial: bool = False,
) -> Response:
    try:
        datos = consultas.exportar_filas(numero, desde, hasta, tipo, sentido, parcial)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    salida = io.StringIO()
    salida.write("\ufeff")
    escritor = csv.writer(salida, delimiter=";")
    escritor.writerow(
        [
            "titular",
            "destino",
            "origen",
            "fecha",
            "hora",
            "duracion_seg",
            "tipo",
            "sentido",
            "imei",
            "imsi",
            "celda",
            "lac",
            "antena",
            "latitud",
            "longitud",
            "operador",
            "tecnologia",
            "roaming",
            "titular_clase",
            "origen_clase",
            "destino_clase",
            "archivo_origen",
        ]
    )
    for fila in datos:
        escritor.writerow(
            [
                fila["titular"],
                fila["destino"] or "",
                fila["origen"] or "",
                fila["fecha"].isoformat() if fila["fecha"] else "",
                fila["hora"].isoformat() if fila["hora"] else "",
                "" if fila["duracion_seg"] is None else fila["duracion_seg"],
                fila["tipo"] or "",
                fila["sentido"] or "",
                fila["imei"] or "",
                fila["imsi"] or "",
                fila["celda"] or "",
                fila["lac"] or "",
                fila["antena"] or "",
                "" if fila["latitud"] is None else fila["latitud"],
                "" if fila["longitud"] is None else fila["longitud"],
                fila["operador"] or "",
                fila["tecnologia"] or "",
                "" if fila["roaming"] is None else ("si" if fila["roaming"] else "no"),
                fila["titular_clase"] or "",
                fila["origen_clase"] or "",
                fila["destino_clase"] or "",
                fila["archivo_origen"],
            ]
        )

    return Response(
        content=salida.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="llamadas.csv"'},
    )


def _montar_frontend() -> None:
    directorio = obtener_settings().directorio_web
    if directorio.is_dir():
        app.mount("/", StaticFiles(directory=str(directorio), html=True), name="web")


_montar_frontend()


def main() -> None:
    import uvicorn

    ajustes = obtener_settings()
    uvicorn.run(
        "cargadatos.api:app",
        host=ajustes.api_host,
        port=ajustes.api_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
