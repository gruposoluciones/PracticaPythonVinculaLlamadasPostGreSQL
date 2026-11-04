"""Tests de normalización de un registro CDR completo."""
from __future__ import annotations

from datetime import date, time

from cargadatos.etl import normalizar_registro


def _normalizar(registro, codigo_pais="51"):
    normalizado, motivo = normalizar_registro(registro, codigo_pais)
    assert motivo is None, motivo
    assert normalizado is not None
    return normalizado


def test_registro_completo():
    registro = {
        "titular": "+51 900 000 001",
        "origen": "51900000001",
        "destino": "51900000002",
        "fecha": "20240115",
        "hora": "101500",
        "duracion": "45",
        "tipo": "voz",
        "sentido": "",
        "imei": "490154203237518",
        "imsi": "716061234567890",
        "celda": "12345",
        "lac": "678",
        "antena": "ANT-01",
        "latitud": "-12.0469",
        "longitud": "-77.0428",
        "operador": "Entel",
        "tecnologia": "4G",
        "roaming": "no",
        "fila_origen": "2",
    }
    normalizado = _normalizar(registro)

    assert normalizado["titular"] == "51900000001"
    assert normalizado["origen"] == "51900000001"
    assert normalizado["destino"] == "51900000002"
    assert normalizado["fecha"] == date(2024, 1, 15)
    assert normalizado["hora"] == time(10, 15)
    assert normalizado["duracion_seg"] == 45
    assert normalizado["tipo"] == "Voz"
    assert normalizado["sentido"] == "Saliente"
    assert normalizado["imei"] == "490154203237518"
    assert normalizado["imsi"] == "716061234567890"
    assert normalizado["celda"] == "12345"
    assert normalizado["lac"] == "678"
    assert normalizado["antena"] == "ANT-01"
    assert normalizado["latitud"] == -12.0469
    assert normalizado["longitud"] == -77.0428
    assert normalizado["operador"] == "Entel"
    assert normalizado["tecnologia"] == "4G"
    assert normalizado["roaming"] is False
    assert normalizado["titular_clase"] == "movil"
    assert normalizado["destino_clase"] == "movil"


def test_campos_ausentes_quedan_en_null():
    normalizado = _normalizar({"titular": "51900000001", "fila_origen": "1"})

    assert normalizado["fecha"] is None
    assert normalizado["hora"] is None
    assert normalizado["duracion_seg"] is None
    assert normalizado["tipo"] is None
    assert normalizado["sentido"] is None
    assert normalizado["imei"] is None
    assert normalizado["imsi"] is None
    assert normalizado["celda"] is None
    assert normalizado["lac"] is None
    assert normalizado["antena"] is None
    assert normalizado["latitud"] is None
    assert normalizado["longitud"] is None
    assert normalizado["operador"] is None
    assert normalizado["tecnologia"] is None
    assert normalizado["roaming"] is None
    assert normalizado["origen_clase"] is None


def test_sentido_entrante_inferido():
    normalizado = _normalizar(
        {
            "titular": "51900000001",
            "origen": "51900000002",
            "destino": "51900000001",
        }
    )
    assert normalizado["sentido"] == "Entrante"


def test_fecha_y_hora_por_componentes():
    normalizado = _normalizar(
        {
            "titular": "51900000001",
            "anio": "2018",
            "mes": "11",
            "dia": "13",
            "hora_num": "11",
            "minuto": "57",
            "segundo": "25",
        }
    )
    assert normalizado["fecha"] == date(2018, 11, 13)
    assert normalizado["hora"] == time(11, 57, 25)


def test_fecha_y_hora_combinadas():
    normalizado = _normalizar(
        {
            "titular": "51900000001",
            "fecha_hora": "2018-11-13 11:57:25",
        }
    )
    assert normalizado["fecha"] == date(2018, 11, 13)
    assert normalizado["hora"] == time(11, 57, 25)


def test_imei_de_longitud_invalida_queda_en_null():
    normalizado = _normalizar(
        {"titular": "51900000001", "imei": "12345"}
    )
    assert normalizado["imei"] is None


def test_coordenadas_fuera_de_rango_quedan_en_null():
    normalizado = _normalizar(
        {
            "titular": "51900000001",
            "latitud": "120",
            "longitud": "200",
        }
    )
    assert normalizado["latitud"] is None
    assert normalizado["longitud"] is None


def test_clasificacion_extranjera():
    normalizado = _normalizar({"titular": "12025550123"})
    assert normalizado["titular_clase"] == "extranjero"


def test_sin_numeros_se_rechaza():
    normalizado, motivo = normalizar_registro({"fecha": "20240115"})
    assert normalizado is None
    assert "sin número" in motivo
