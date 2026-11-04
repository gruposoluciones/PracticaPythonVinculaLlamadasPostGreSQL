"""Tests de detección de columnas CDR por cabecera y por valores."""
from __future__ import annotations

import pytest

from cargadatos import mapeo


def test_cabecera_en_ingles():
    encabezados = [
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
    detectado = mapeo.detectar_por_cabecera(encabezados)
    assert detectado["titular"] == 0
    assert detectado["destino"] == 1
    assert detectado["origen"] == 2
    assert detectado["fecha"] == 3
    assert detectado["hora"] == 4
    assert detectado["duracion"] == 5
    assert detectado["tipo"] == 6
    assert detectado["sentido"] == 7
    assert detectado["imei"] == 8
    assert detectado["imsi"] == 9
    assert detectado["celda"] == 10
    assert detectado["lac"] == 11
    assert detectado["antena"] == 12
    assert detectado["latitud"] == 13
    assert detectado["longitud"] == 14
    assert detectado["operador"] == 15
    assert detectado["tecnologia"] == 16
    assert detectado["roaming"] == 17


def test_cabecera_en_espanol_con_acentos():
    encabezados = [
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
    detectado = mapeo.detectar_por_cabecera(encabezados)
    assert detectado["titular"] == 0
    assert detectado["destino"] == 1
    assert detectado["origen"] == 2
    assert detectado["duracion"] == 5
    assert detectado["sentido"] == 7
    assert detectado["celda"] == 9
    assert detectado["antena"] == 10


def test_fecha_y_hora_combinadas():
    detectado = mapeo.detectar_por_cabecera(["MSISDN", "Fecha y hora", "Duración"])
    assert detectado["fecha_hora"] == 1
    assert detectado["duracion"] == 2


def test_deteccion_por_valores():
    matriz = [
        ["51900000001", "51900000002", "51900000003", "20240115", "101500", "45", "Voz", "Entrante", "490154203237518"],
        ["51900000001", "51900000004", "51900000005", "20240116", "111500", "50", "Voz", "Saliente", "490154203237518"],
        ["51900000001", "51900000006", "51900000007", "20240117", "121500", "55", "SMS", "Entrante", "490154203237518"],
    ]
    detectado = mapeo.detectar_por_valores(matriz)
    assert detectado["titular"] == 0
    assert detectado["destino"] == 1
    assert detectado["origen"] == 2
    assert detectado["fecha"] == 3
    assert detectado["hora"] == 4
    assert detectado["duracion"] == 5
    assert detectado["tipo"] == 6
    assert detectado["sentido"] == 7
    assert detectado["imei"] == 8


def test_parsear_mapeo():
    resultado = mapeo.parsear_mapeo("titular=0, origen=3, imei=17")
    assert resultado == {"titular": 0, "origen": 3, "imei": 17}


@pytest.mark.parametrize(
    "texto",
    ["", "titular", "titular=x", "columna_rara=1", "titular=-1"],
)
def test_parsear_mapeo_invalido(texto):
    with pytest.raises(ValueError):
        mapeo.parsear_mapeo(texto)


def test_campos_incluye_alternos():
    assert "fecha_alterna" in mapeo.CAMPOS
    assert "hora_alterna" in mapeo.CAMPOS
