"""Lectura y detección de formato de archivos Excel y CSV.

Formatos soportados (ver AGENTS.md, sección 6):

* 17 columnas con cabecera: ``entel_base.xlsx`` (incluye ``Número origen``).
* 16 columnas sin cabecera (o con cabecera): sin columna de origen.

El lector no interpreta fechas ni horas: entrega los valores crudos y deja la
normalización en ``cargadatos.normalizacion``.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

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
}

# Posiciones (0-based) de cada campo según el layout.
LAYOUT_17 = {
    "titular": 0,
    "destino": 1,
    "origen": 3,
    "fecha": 4,
    "fecha_alterna": 8,
    "hora": 13,
    "hora_alterna": 9,
    "duracion": 14,
    "tipo": 15,
    "sentido": 16,
}

LAYOUT_16 = {
    "titular": 0,
    "destino": 1,
    "origen": None,
    "fecha": 3,
    "fecha_alterna": 7,
    "hora": 12,
    "hora_alterna": 8,
    "duracion": 13,
    "tipo": 14,
    "sentido": 15,
}


class FormatoNoSoportado(ValueError):
    """El archivo no corresponde a ninguno de los layouts conocidos."""


@dataclass(frozen=True)
class TablaLeida:
    """Resultado de leer un archivo: formato detectado y filas crudas."""

    formato: str
    filas: list[dict[str, str]]
    total_filas: int


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
    # Segunda heurística: la cabecera no contiene teléfonos de 8+ dígitos.
    return bool(textos) and not any(
        sum(caracter.isdigit() for caracter in valor) >= 8 for valor in textos
    )


def _leer_dataframe(ruta: Path) -> pd.DataFrame:
    sufijo = ruta.suffix.lower()
    if sufijo == ".csv":
        # sep=None permite detectar ';' o ',' automáticamente.
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


def interpretar_dataframe(df: pd.DataFrame) -> TablaLeida:
    """Detecta el layout y extrae las filas en un diccionario por campo."""
    if df.empty:
        raise FormatoNoSoportado("El archivo no contiene filas.")

    matriz = [[_celda(valor) for valor in fila] for fila in df.itertuples(index=False, name=None)]
    if not matriz:
        raise FormatoNoSoportado("El archivo no contiene filas.")

    tiene_cabecera = _parece_cabecera(matriz[0])
    datos = matriz[1:] if tiene_cabecera else matriz

    numero_columnas = max(len(fila) for fila in matriz)
    if numero_columnas >= 17:
        layout = LAYOUT_17
        formato = "base_17" + ("_con_cabecera" if tiene_cabecera else "_sin_cabecera")
    elif numero_columnas == 16:
        layout = LAYOUT_16
        formato = "sin_origen_16" + ("_con_cabecera" if tiene_cabecera else "_sin_cabecera")
    else:
        raise FormatoNoSoportado(
            f"Se esperaban 16 o 17 columnas y se encontraron {numero_columnas}."
        )

    filas: list[dict[str, str]] = []
    for numero_fila, fila in enumerate(datos, start=2 if tiene_cabecera else 1):
        if not any(valor.strip() for valor in fila):
            continue
        completa = fila + [""] * (numero_columnas - len(fila))
        registro = {
            campo: (completa[indice] if indice is not None else "")
            for campo, indice in layout.items()
        }
        registro["fila_origen"] = str(numero_fila)
        filas.append(registro)

    return TablaLeida(formato=formato, filas=filas, total_filas=len(filas))


def leer_archivo(ruta: str | Path) -> TablaLeida:
    """Lee un Excel/CSV y devuelve sus filas crudas con el formato detectado."""
    ruta = Path(ruta)
    if not ruta.is_file():
        raise FileNotFoundError(f"No existe el archivo: {ruta}")
    if not es_archivo_soportado(ruta.name):
        raise FormatoNoSoportado(
            f"Extensión no soportada: {ruta.suffix}. Use .xlsx, .xls o .csv."
        )
    return interpretar_dataframe(_leer_dataframe(ruta))
