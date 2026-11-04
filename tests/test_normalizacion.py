"""Tests de normalización: teléfonos, fechas, horas y duraciones."""
from __future__ import annotations

from datetime import date, datetime, time

import pytest

from cargadatos import normalizacion as norm


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("51977369934", "51977369934"),
        ("+51 977 369 934", "51977369934"),
        ("(51) 977-369-934", "51977369934"),
        ("5.1977369934E10", "51977369934"),
        ("51977369934.0", "51977369934"),
        (51977369934, "51977369934"),
        ("051977369934", "051977369934"),
    ],
)
def test_normalizar_telefono_valido(entrada, esperado):
    assert norm.normalizar_telefono(entrada) == esperado


@pytest.mark.parametrize("entrada", [None, "", "   ", "123", "abc", "1234567890123456"])
def test_normalizar_telefono_invalido(entrada):
    assert norm.normalizar_telefono(entrada) is None


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("20181113", date(2018, 11, 13)),
        ("13/11/2018", date(2018, 11, 13)),
        ("13-11-2018", date(2018, 11, 13)),
        ("2018-11-13", date(2018, 11, 13)),
        ("2018-11-13 00:00:00", date(2018, 11, 13)),
        (43417, date(2018, 11, 13)),
        ("43417", date(2018, 11, 13)),
        (date(2020, 1, 2), date(2020, 1, 2)),
        (datetime(2020, 1, 2, 9, 30), date(2020, 1, 2)),
    ],
)
def test_normalizar_fecha(entrada, esperado):
    assert norm.normalizar_fecha(entrada) == esperado


@pytest.mark.parametrize("entrada", [None, "", "no es fecha", "2018-13-40", 0, -5])
def test_normalizar_fecha_invalida(entrada):
    assert norm.normalizar_fecha(entrada) is None


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("115725", time(11, 57, 25)),
        ("081313", time(8, 13, 13)),
        ("81313", time(8, 13, 13)),
        ("11:57:25", time(11, 57, 25)),
        ("8:13", time(8, 13, 0)),
        (0.49820601851851853, time(11, 57, 25)),
        ("0", time(0, 0, 0)),
        (time(23, 59, 59), time(23, 59, 59)),
        (datetime(2020, 1, 1, 7, 5, 3), time(7, 5, 3)),
    ],
)
def test_normalizar_hora(entrada, esperado):
    assert norm.normalizar_hora(entrada) == esperado


@pytest.mark.parametrize("entrada", [None, "", "240000", "99:99:99", "abc"])
def test_normalizar_hora_invalida(entrada):
    assert norm.normalizar_hora(entrada) is None


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [(None, 0), ("", 0), ("0", 0), (34, 34), ("34", 34), ("34.0", 34), ("34.9", 34)],
)
def test_normalizar_duracion(entrada, esperado):
    assert norm.normalizar_duracion(entrada) == esperado


@pytest.mark.parametrize("entrada", ["-1", "-0.5", "abc"])
def test_normalizar_duracion_invalida(entrada):
    assert norm.normalizar_duracion(entrada) is None


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [("voz", "Voz"), ("VOZ", "Voz"), ("sms", "SMS"), ("DATOS", "Datos"), (None, None)],
)
def test_normalizar_tipo(entrada, esperado):
    assert norm.normalizar_tipo(entrada) == esperado


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("entrante", "Entrante"),
        ("IN", "Entrante"),
        ("saliente", "Saliente"),
        ("OUT", "Saliente"),
        (None, None),
    ],
)
def test_normalizar_sentido(entrada, esperado):
    assert norm.normalizar_sentido(entrada) == esperado


def test_hash_fila_es_estable_y_sensible_al_contenido():
    base = dict(
        titular="51900000001",
        origen="51900000002",
        destino="51900000001",
        fecha=date(2024, 1, 15),
        hora=time(10, 15, 0),
        duracion_seg=45,
        tipo="Voz",
        sentido="Entrante",
    )
    primero = norm.calcular_hash_fila(**base)
    segundo = norm.calcular_hash_fila(**base)
    assert primero == segundo == norm.calcular_hash_fila(**base)

    distinto = norm.calcular_hash_fila(**{**base, "duracion_seg": 46})
    assert distinto != primero


def test_enmascarar_telefono():
    assert norm.enmascarar("51977369934") == "519****9934"
    assert norm.enmascarar(None) == ""
