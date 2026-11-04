"""Tests del lector de Excel/CSV y de la detección de layout."""
from __future__ import annotations

import pandas as pd
import pytest

from cargadatos.excel_reader import (
    FormatoNoSoportado,
    es_archivo_soportado,
    interpretar_dataframe,
    leer_archivo,
)

CABECERA_17 = [
    "Línea Titular", "Número destino", "", "Número origen", "Fecha", "Año",
    "mes", "dia", "fecha", "Hora", "hora", "minuto", "segundo", "hora",
    "Duración (Segundos)", "tipo", "llamada entrante/saliente",
]

FILA_17 = [
    "51900000001", "51900000002", "51900000001", "51900000003", "20240115",
    "2024", "1", "15", "15/01/2024", "101500", "10", "15", "0", "10:15:00",
    "45", "Voz", "Entrante",
]

# Layout de 16 columnas = el de 17 sin "Número origen".
CABECERA_16 = [valor for indice, valor in enumerate(CABECERA_17) if indice != 3]
FILA_16 = [valor for indice, valor in enumerate(FILA_17) if indice != 3]


def _dataframe(filas):
    return pd.DataFrame(filas, dtype=str)


def test_layout_17_con_cabecera():
    tabla = interpretar_dataframe(_dataframe([CABECERA_17, FILA_17]))
    assert tabla.formato == "base_17_con_cabecera"
    assert tabla.total_filas == 1
    fila = tabla.filas[0]
    assert fila["titular"] == "51900000001"
    assert fila["origen"] == "51900000003"
    assert fila["destino"] == "51900000002"
    assert fila["fecha"] == "20240115"
    assert fila["hora"] == "10:15:00"
    assert fila["duracion"] == "45"
    assert fila["tipo"] == "Voz"
    assert fila["sentido"] == "Entrante"
    assert fila["fila_origen"] == "2"


def test_layout_16_sin_cabecera():
    tabla = interpretar_dataframe(_dataframe([FILA_16]))
    assert tabla.formato == "sin_origen_16_sin_cabecera"
    fila = tabla.filas[0]
    assert fila["origen"] == ""
    assert fila["fecha"] == "20240115"
    assert fila["hora"] == "10:15:00"
    assert fila["duracion"] == "45"
    assert fila["fila_origen"] == "1"


def test_layout_16_con_cabecera():
    tabla = interpretar_dataframe(_dataframe([CABECERA_16, FILA_16]))
    assert tabla.formato == "sin_origen_16_con_cabecera"
    assert tabla.total_filas == 1
    assert tabla.filas[0]["fila_origen"] == "2"


def test_filas_vacias_se_omiten():
    tabla = interpretar_dataframe(_dataframe([FILA_16, [""] * 16]))
    assert tabla.total_filas == 1


def test_numero_de_columnas_no_soportado():
    with pytest.raises(FormatoNoSoportado):
        interpretar_dataframe(_dataframe([["a", "b", "c"]]))


def test_archivo_vacio():
    with pytest.raises(FormatoNoSoportado):
        interpretar_dataframe(pd.DataFrame())


def test_leer_xlsx(tmp_path):
    ruta = tmp_path / "muestra.xlsx"
    _dataframe([FILA_16]).to_excel(ruta, index=False, header=False)

    tabla = leer_archivo(ruta)
    assert tabla.formato == "sin_origen_16_sin_cabecera"
    assert tabla.filas[0]["titular"] == "51900000001"


def test_leer_csv_con_punto_y_coma(tmp_path):
    ruta = tmp_path / "muestra.csv"
    ruta.write_text(";".join(FILA_16) + "\n", encoding="utf-8")

    tabla = leer_archivo(ruta)
    assert tabla.formato == "sin_origen_16_sin_cabecera"
    assert tabla.filas[0]["sentido"] == "Entrante"


def test_extensiones_soportadas():
    assert es_archivo_soportado("datos.xlsx")
    assert es_archivo_soportado("datos.XLS")
    assert es_archivo_soportado("datos.csv")
    assert not es_archivo_soportado("datos.txt")


def test_archivo_inexistente(tmp_path):
    with pytest.raises(FileNotFoundError):
        leer_archivo(tmp_path / "no_existe.xlsx")
