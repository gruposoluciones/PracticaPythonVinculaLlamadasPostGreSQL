"""Tests de construcción de filtros y validaciones (sin base de datos)."""
from __future__ import annotations

from datetime import date

import pytest

from cargadatos import consultas


def test_sin_filtros_devuelve_true():
    where, parametros = consultas.construir_filtros()
    assert where == "TRUE"
    assert parametros == []


def test_filtro_numero_exacto():
    where, parametros = consultas.construir_filtros(numero="+51 900 000 001")
    assert "titular = %s" in where
    assert parametros == ["51900000001", "51900000001", "51900000001"]


def test_filtro_numero_parcial():
    where, parametros = consultas.construir_filtros(numero="9000", parcial=True)
    assert "LIKE %s" in where
    assert parametros == ["%9000%", "%9000%", "%9000%"]


def test_filtro_numero_sin_digitos():
    with pytest.raises(ValueError):
        consultas.construir_filtros(numero="abc")


def test_filtro_fechas_y_tipo():
    where, parametros = consultas.construir_filtros(
        desde="2024-01-01", hasta="2024-01-31", tipo="Voz", sentido="Entrante"
    )
    assert "fecha >= %s" in where
    assert "fecha <= %s" in where
    assert parametros == [
        date(2024, 1, 1),
        date(2024, 1, 31),
        "Voz",
        "Entrante",
    ]


def test_rango_de_fechas_invertido():
    with pytest.raises(ValueError):
        consultas.construir_filtros(desde="2024-02-01", hasta="2024-01-01")


def test_fecha_invalida():
    with pytest.raises(ValueError):
        consultas.construir_filtros(desde="ayer")


def test_agregado_no_valido():
    with pytest.raises(ValueError):
        consultas.agregados(por="inexistente")


def test_vincular_valida_numeros_sin_base_de_datos():
    with pytest.raises(ValueError):
        consultas.vincular("abc", "def")
    with pytest.raises(ValueError):
        consultas.vincular("51900000001", "51900000001")
