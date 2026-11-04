"""Lectura de Excel/CSV con detección inteligente de columnas CDR.

El lector combina tres estrategias:

1. Cabecera con sinónimos (español/inglés): ``MSISDN``, ``IMEI``, ``Cell ID``…
2. Layouts legados de 16/17 columnas.
3. Inferencia por contenido cuando no hay cabecera reconocible.

Los valores se entregan en crudo; la normalización vive en
``cargadatos.normalizacion``.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from cargadatos import mapeo as deteccion_mapeo

EXTENSIONES_SOPORTADAS = {".xlsx", ".xlsm", ".xls", ".csv"}

ETIQUETAS_CABECERA = {
    "linea titular",
    "línea titular",
    "numero destino",
    "número destino",
    "numero origen",
    "número origen",
    "duracion (segundos)",
    "duración (segundos)",
    "llamada entrante/saliente",
    "imei",
    "imsi",
    "msisdn",
    "cell id",
    "celda",
    "fecha",
    "hora",
}

# Layout legado de 17 columnas (con "Número origen").
LEGACY_17 = {
    "titular": 0,
    "destino": 1,
    "origen": 3,
    "fecha": 4,
    "fecha_alterna": 8,
    "hora": 13,
    "hora_alterna": 9,
    "anio": 5,
    "mes": 6,
    "dia": 7,
    "hora_num": 10,
    "minuto": 11,
    "segundo": 12,
    "duracion": 14,
    "tipo": 15,
    "sentido": 16,
}

# Layout legado de 16 columnas (sin "Número origen").
LEGACY_16 = {
    "titular": 0,
    "destino": 1,
    "fecha": 3,
    "fecha_alterna": 7,
    "hora": 12,
    "hora_alterna": 8,
    "anio": 4,
    "mes": 5,
    "dia": 6,
    "hora_num": 9,
    "minuto": 10,
    "segundo": 11,
    "duracion": 13,
    "tipo": 14,
    "sentido": 15,
}


class FormatoNoSoportado(ValueError):
    """El archivo no contiene columnas reconocibles de un CDR."""


@dataclass(frozen=True)
class TablaLeida:
    """Formato detectado, mapeo de columnas y filas crudas."""

    formato: str
    filas: list[dict[str, str]]
    total_filas: int
    mapeo: dict[str, int]


def es_archivo_soportado(nombre: str) -> bool:
    return Path(nombre).suffix.lower() in EXTENSIONES_SOPORTADAS


def _celda(valor: object) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and valor != valor:
        return ""
    resultado = str(valor).strip()
    return "" if resultado.lower() in {"nan", "none", "nat"} else resultado


def _parece_cabecera(fila: list[str]) -> bool:
    textos = {valor.strip().lower() for valor in fila if valor.strip()}
    if textos & ETIQUETAS_CABECERA:
        return True
    return bool(textos) and not any(
        sum(caracter.isdigit() for caracter in valor) >= 8 for valor in textos
    )


def _leer_dataframe(ruta: Path) -> pd.DataFrame:
    sufijo = ruta.suffix.lower()
    if sufijo == ".csv":
        return pd.read_csv(
            ruta,
            header=None,
            dtype=str,
            sep=None,
            engine="python",
            encoding="utf-8-sig",
            keep_default_na=False,
        )
    motor = "xlrd" if sufijo == ".xls" else "openpyxl"
    return pd.read_excel(
        ruta,
        header=None,
        dtype=str,
        engine=motor,
        keep_default_na=False,
    )


def _tiene_numeros(mapeo: dict[str, int]) -> bool:
    return any(campo in mapeo for campo in ("titular", "origen", "destino"))


def _validar_mapeo(mapeo: dict[str, int], numero_columnas: int) -> None:
    for campo, indice in mapeo.items():
        if indice < 0 or indice >= numero_columnas:
            raise FormatoNoSoportado(
                f"La columna {indice} de '{campo}' está fuera de rango "
                f"(el archivo tiene {numero_columnas} columnas)."
            )


def _ratio_con_hora(valores: list[str]) -> float:
    no_vacios = [valor for valor in valores if valor.strip()]
    if not no_vacios:
        return 0.0
    return sum(1 for valor in no_vacios if ":" in valor) / len(no_vacios)


def _preferir_hora_formateada(
    mapeo: dict[str, int], datos: list[list[str]]
) -> None:
    """Si una columna de hora tiene ``HH:MM:SS``, úsala como hora principal."""
    if "hora" not in mapeo:
        return
    muestra = datos[:200]

    def valores_de(campo: str) -> list[str]:
        indice = mapeo[campo]
        return [fila[indice] if indice < len(fila) else "" for fila in muestra]

    if _ratio_con_hora(valores_de("hora")) >= 0.8:
        return

    for alternativa in ("hora_alterna", "hora_num"):
        if alternativa not in mapeo:
            continue
        if _ratio_con_hora(valores_de(alternativa)) >= 0.8:
            mapeo["hora"], mapeo[alternativa] = mapeo[alternativa], mapeo["hora"]
            return


def interpretar_dataframe(
    df: pd.DataFrame,
    mapeo_forzado: dict[str, int] | None = None,
) -> TablaLeida:
    """Detecta el formato y extrae las filas con su mapeo de columnas."""
    if df.empty:
        raise FormatoNoSoportado("El archivo no contiene filas.")

    matriz = [[_celda(valor) for valor in fila] for fila in df.itertuples(index=False, name=None)]
    if not matriz:
        raise FormatoNoSoportado("El archivo no contiene filas.")

    tiene_cabecera = False
    indice_cabecera, mapeo_cabecera = deteccion_mapeo.detectar_cabecera(matriz)
    if indice_cabecera is not None:
        tiene_cabecera = True
    elif _parece_cabecera(matriz[0]):
        indice_cabecera = 0
        tiene_cabecera = True
        mapeo_cabecera = {}

    datos = matriz[indice_cabecera + 1 :] if tiene_cabecera else matriz
    numero_columnas = max(len(fila) for fila in matriz)

    if mapeo_forzado:
        mapeo = dict(mapeo_forzado)
        formato = "manual"
    elif tiene_cabecera:
        mapeo = mapeo_cabecera
        if _tiene_numeros(mapeo):
            formato = "cdr_con_cabecera"
        elif numero_columnas >= 17:
            mapeo = dict(LEGACY_17)
            formato = "legacy_17_con_cabecera"
        elif numero_columnas == 16:
            mapeo = dict(LEGACY_16)
            formato = "legacy_16_con_cabecera"
        else:
            mapeo = deteccion_mapeo.detectar_por_valores(datos)
            formato = "cdr_inferido"
    else:
        if numero_columnas >= 17:
            mapeo = dict(LEGACY_17)
            formato = "legacy_17_sin_cabecera"
        elif numero_columnas == 16:
            mapeo = dict(LEGACY_16)
            formato = "legacy_16_sin_cabecera"
        else:
            mapeo = deteccion_mapeo.detectar_por_valores(datos)
            formato = "cdr_inferido"

    if not _tiene_numeros(mapeo):
        inferido = deteccion_mapeo.detectar_por_valores(datos)
        if _tiene_numeros(inferido):
            mapeo = inferido
            formato = "cdr_inferido"
        else:
            raise FormatoNoSoportado(
                "No se pudo identificar ninguna columna de número telefónico. "
                "Use --mapeo para indicarla manualmente."
            )

    _validar_mapeo(mapeo, numero_columnas)
    if formato == "cdr_con_cabecera":
        _preferir_hora_formateada(mapeo, datos)

    filas: list[dict[str, str]] = []
    inicio = (indice_cabecera + 2) if tiene_cabecera else 1
    for numero_fila, fila in enumerate(datos, start=inicio):
        if not any(valor.strip() for valor in fila):
            continue
        completa = fila + [""] * (numero_columnas - len(fila))
        registro = {
            campo: completa[indice] for campo, indice in mapeo.items()
        }
        registro["fila_origen"] = str(numero_fila)
        filas.append(registro)

    return TablaLeida(
        formato=formato,
        filas=filas,
        total_filas=len(filas),
        mapeo=mapeo,
    )


def leer_archivo(
    ruta: str | Path,
    mapeo_forzado: dict[str, int] | None = None,
) -> TablaLeida:
    """Lee un Excel/CSV y devuelve sus filas crudas con el mapeo detectado."""
    ruta = Path(ruta)
    if not ruta.is_file():
        raise FileNotFoundError(f"No existe el archivo: {ruta}")
    if not es_archivo_soportado(ruta.name):
        raise FormatoNoSoportado(
            f"Extensión no soportada: {ruta.suffix}. Use .xlsx, .xls o .csv."
        )
    return interpretar_dataframe(_leer_dataframe(ruta), mapeo_forzado)
