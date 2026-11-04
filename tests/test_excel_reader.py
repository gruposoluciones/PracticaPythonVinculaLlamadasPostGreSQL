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
    assert tabla.formato == "cdr_con_cabecera"
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
    assert tabla.formato == "legacy_16_sin_cabecera"
    fila = tabla.filas[0]
    assert fila.get("origen", "") == ""
    assert fila["fecha"] == "20240115"
    assert fila["hora"] == "10:15:00"
    assert fila["duracion"] == "45"
    assert fila["fila_origen"] == "1"


def test_layout_16_con_cabecera():
    tabla = interpretar_dataframe(_dataframe([CABECERA_16, FILA_16]))
    assert tabla.formato == "cdr_con_cabecera"
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
    assert tabla.formato == "legacy_16_sin_cabecera"
    assert tabla.filas[0]["titular"] == "51900000001"


def test_leer_csv_con_punto_y_coma(tmp_path):
    ruta = tmp_path / "muestra.csv"
    ruta.write_text(";".join(FILA_16) + "\n", encoding="utf-8")

    tabla = leer_archivo(ruta)
    assert tabla.formato == "legacy_16_sin_cabecera"
    assert tabla.filas[0]["sentido"] == "Entrante"


def test_extensiones_soportadas():
    assert es_archivo_soportado("datos.xlsx")
    assert es_archivo_soportado("datos.XLS")
    assert es_archivo_soportado("datos.csv")
    assert not es_archivo_soportado("datos.txt")


def test_archivo_inexistente(tmp_path):
    with pytest.raises(FileNotFoundError):
        leer_archivo(tmp_path / "no_existe.xlsx")


CABECERA_CDR = [
    "MSISDN",
    "Called Number",
    "Calling Number",
    "Start Date",
    "Start Time",
    "Duration",
    "Call Type",
    "Direction",
    "IMEI",
    "IMSI",
    "Cell ID",
    "LAC",
    "Site",
    "Latitude",
    "Longitude",
    "Operator",
    "Technology",
    "Roaming",
]

FILA_CDR = [
    "51900000001",
    "51900000002",
    "51900000003",
    "2024-01-15",
    "10:15:00",
    "45",
    "Voz",
    "Saliente",
    "490154203237518",
    "716061234567890",
    "12345",
    "678",
    "ANT-01",
    "-12.0469",
    "-77.0428",
    "Entel",
    "4G",
    "no",
]


def test_cabecera_cdr_completa_en_ingles():
    tabla = interpretar_dataframe(_dataframe([CABECERA_CDR, FILA_CDR]))
    assert tabla.formato == "cdr_con_cabecera"
    fila = tabla.filas[0]
    assert fila["titular"] == "51900000001"
    assert fila["destino"] == "51900000002"
    assert fila["origen"] == "51900000003"
    assert fila["fecha"] == "2024-01-15"
    assert fila["hora"] == "10:15:00"
    assert fila["duracion"] == "45"
    assert fila["tipo"] == "Voz"
    assert fila["sentido"] == "Saliente"
    assert fila["imei"] == "490154203237518"
    assert fila["imsi"] == "716061234567890"
    assert fila["celda"] == "12345"
    assert fila["lac"] == "678"
    assert fila["antena"] == "ANT-01"
    assert fila["latitud"] == "-12.0469"
    assert fila["longitud"] == "-77.0428"
    assert fila["operador"] == "Entel"
    assert fila["tecnologia"] == "4G"
    assert fila["roaming"] == "no"


def test_cabecera_cdr_con_sinonimos_en_espanol():
    cabecera = [
        "Línea Titular",
        "Número destino",
        "Número origen",
        "Fecha",
        "Hora",
        "Duración (Segundos)",
        "tipo",
        "llamada entrante/saliente",
        "IMEI",
        "Celda",
        "Antena",
    ]
    fila = [
        "51900000001",
        "51900000002",
        "51900000003",
        "20240115",
        "10:15:00",
        "45",
        "Voz",
        "Entrante",
        "490154203237518",
        "12345",
        "ANT-01",
    ]
    tabla = interpretar_dataframe(_dataframe([cabecera, fila]))
    assert tabla.formato == "cdr_con_cabecera"
    assert tabla.filas[0]["celda"] == "12345"
    assert tabla.filas[0]["antena"] == "ANT-01"
    assert tabla.filas[0]["sentido"] == "Entrante"


def test_inferencia_por_valores_sin_cabecera():
    filas = [
        ["51900000001", "51900000002", "51900000003", "20240115", "101500", "45", "Voz", "Entrante", "490154203237518"],
        ["51900000001", "51900000004", "51900000005", "20240116", "111500", "50", "Voz", "Saliente", "490154203237518"],
        ["51900000001", "51900000006", "51900000007", "20240117", "121500", "55", "Voz", "Entrante", "490154203237518"],
        ["51900000001", "51900000008", "51900000009", "20240118", "131500", "60", "SMS", "Saliente", "490154203237518"],
        ["51900000001", "51900000010", "51900000011", "20240119", "141500", "65", "Voz", "Entrante", "490154203237518"],
    ]
    tabla = interpretar_dataframe(_dataframe(filas))
    assert tabla.formato == "cdr_inferido"
    assert tabla.filas[0]["titular"] == "51900000001"
    assert tabla.filas[0]["destino"] == "51900000002"
    assert tabla.filas[0]["origen"] == "51900000003"
    assert tabla.filas[0]["fecha"] == "20240115"
    assert tabla.filas[0]["hora"] == "101500"
    assert tabla.filas[0]["duracion"] == "45"
    assert tabla.filas[0]["tipo"] == "Voz"
    assert tabla.filas[0]["sentido"] == "Entrante"
    assert tabla.filas[0]["imei"] == "490154203237518"


def test_mapeo_forzado():
    tabla = interpretar_dataframe(
        _dataframe([FILA_16]),
        mapeo_forzado={
            "titular": 0,
            "destino": 1,
            "fecha": 3,
            "hora": 12,
            "duracion": 13,
            "tipo": 14,
            "sentido": 15,
        },
    )
    assert tabla.formato == "manual"
    assert tabla.filas[0]["titular"] == "51900000001"


def test_cabecera_despues_de_una_fila_de_titulo():
    titulo = ["CONSULTA DE LISTA VINCULACIONES (TABLA 2)"] + [""] * 8
    cabecera = [
        "Item",
        "imei",
        "abonado",
        "fechahora",
        "empresaoperadora",
        "tipoabonado",
        "tipodocabonado",
        "numerodoc",
        "relacion",
    ]
    fila = [
        "1",
        "861731050593753",
        "907976887",
        "2026-06-13 12:02:23",
        "ENTEL PERU S.A.",
        "Persona natural",
        "Pasaporte",
        "PTP004321502",
        "Vinculación",
    ]
    tabla = interpretar_dataframe(_dataframe([titulo, cabecera, fila]))

    assert tabla.formato == "cdr_con_cabecera"
    assert tabla.filas[0]["fila_origen"] == "3"
    assert tabla.filas[0]["imei"] == "861731050593753"
    assert tabla.filas[0]["titular"] == "907976887"
    assert tabla.filas[0]["fecha_hora"] == "2026-06-13 12:02:23"
    assert tabla.filas[0]["operador"] == "ENTEL PERU S.A."
    assert "celda" not in tabla.filas[0]
