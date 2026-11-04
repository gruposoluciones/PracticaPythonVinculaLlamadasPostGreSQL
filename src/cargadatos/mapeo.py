"""Detección inteligente de columnas en archivos CDR.

Prioridad:

1. **Cabecera**: sinónimos en español/inglés (``MSISDN``, ``IMEI``, ``Cell ID``…).
2. **Layout legado**: los formatos de 16/17 columnas ya soportados.
3. **Inferencia por valores**: teléfonos, fechas, horas, duración, tipo, sentido…
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, time

from cargadatos import normalizacion as norm

# Campo canónico -> frases normalizadas que lo identifican en una cabecera.
SINONIMOS: dict[str, tuple[str, ...]] = {
    "titular": (
        "linea titular",
        "linea",
        "titular",
        "numero titular",
        "numero linea",
        "telefono titular",
        "msisdn",
        "a party",
        "aparty",
        "suscriptor",
        "abonado",
    ),
    "origen": (
        "numero origen",
        "origen",
        "numero llamante",
        "llamante",
        "numero que llama",
        "source",
        "from",
        "calling",
        "calling number",
        "a number",
        "msisdn origen",
    ),
    "destino": (
        "numero destino",
        "destino",
        "destino llamada",
        "numero llamado",
        "llamado",
        "numero receptor",
        "b party",
        "bparty",
        "b number",
        "called number",
        "to",
        "msisdn destino",
        "numero b",
    ),
    "fecha_hora": (
        "fecha hora",
        "fecha y hora",
        "fechahora",
        "fecha hora llamada",
        "timestamp",
        "datetime",
        "start datetime",
        "fecha inicio llamada",
    ),
    "fecha": (
        "fecha",
        "fecha llamada",
        "fecha de llamada",
        "fecha inicio",
        "call date",
        "start date",
        "date",
    ),
    "hora": (
        "hora",
        "hora llamada",
        "hora de llamada",
        "hora inicio",
        "start time",
        "time",
    ),
    "duracion": (
        "duracion",
        "duracion segundos",
        "duracion llamada",
        "duration",
        "duration seconds",
        "call duration",
        "tiempo",
        "segundos duracion",
    ),
    "tipo": (
        "tipo",
        "tipo llamada",
        "tipo de llamada",
        "call type",
        "servicio",
        "service",
        "tipo servicio",
    ),
    "sentido": (
        "sentido",
        "direccion",
        "direction",
        "entrante saliente",
        "llamada entrante saliente",
        "call direction",
        "in out",
    ),
    "imei": ("imei", "imei sv", "imeisv", "equipo", "device", "terminal"),
    "imsi": ("imsi", "numero sim", "sim"),
    "celda": (
        "celda",
        "cell",
        "cell id",
        "cellid",
        "id celda",
        "cgi",
        "ecgi",
        "cell identity",
        "ci",
    ),
    "lac": (
        "lac",
        "lac id",
        "tac",
        "location area code",
        "tracking area code",
    ),
    "antena": (
        "antena",
        "antenna",
        "sitio",
        "site",
        "estacion base",
        "bts",
        "enodeb",
        "nodeb",
        "sector",
    ),
    "latitud": ("latitud", "latitude", "lat"),
    "longitud": ("longitud", "longitude", "lon", "lng", "long"),
    "operador": (
        "operador",
        "operator",
        "carrier",
        "red",
        "network",
        "proveedor",
        "empresaoperadora",
        "empresa operadora",
        "empresa",
    ),
    "tecnologia": (
        "tecnologia",
        "technology",
        "rat",
        "tipo red",
        "generacion",
    ),
    "roaming": ("roaming", "itinerancia", "es roaming"),
    "anio": ("ano", "anio", "year"),
    "mes": ("mes", "month"),
    "dia": ("dia", "day"),
    "hora_num": ("hora", "hour"),
    "minuto": ("minuto", "minutos", "minute", "min"),
    "segundo": ("segundo", "segundos", "second", "sec"),
}

# Campos cortos o ambiguos que solo se aceptan por coincidencia exacta.
SOLO_EXACTO = {
    "anio",
    "mes",
    "dia",
    "hora_num",
    "minuto",
    "segundo",
    "lac",
    "latitud",
    "longitud",
    "imei",
    "imsi",
    "tipo",
    "sentido",
    "roaming",
    "celda",
    "destino",
}

CAMPOS = tuple(SINONIMOS.keys()) + ("fecha_alterna", "hora_alterna")

_SINONIMO_A_CAMPO: dict[str, str] = {}
for _campo, _frases in SINONIMOS.items():
    for _frase in _frases:
        _SINONIMO_A_CAMPO.setdefault(_frase, _campo)


def normalizar_encabezado(valor: object) -> str:
    """Minúsculas, sin acentos y sin puntuación."""
    crudo = "" if valor is None else str(valor)
    sin_acentos = (
        unicodedata.normalize("NFKD", crudo).encode("ascii", "ignore").decode("ascii")
    )
    limpio = re.sub(r"[^a-z0-9]+", " ", sin_acentos.lower()).strip()
    return re.sub(r"\s+", " ", limpio)


def _campo_libre(campo: str, mapeo: dict[str, int]) -> str | None:
    if campo not in mapeo:
        return campo
    if campo == "hora":
        for alternativa in ("hora_num", "hora_alterna"):
            if alternativa not in mapeo:
                return alternativa
    if campo == "fecha" and "fecha_alterna" not in mapeo:
        return "fecha_alterna"
    return None


def detectar_cabecera(
    matriz: list[list[str]], max_filas: int = 20
) -> tuple[int | None, dict[str, int]]:
    """Busca la fila de cabecera aunque haya títulos encima.

    Devuelve ``(índice, mapeo)`` o ``(None, {})`` si no hay cabecera
    reconocible.
    """
    mejor_indice: int | None = None
    mejor_mapeo: dict[str, int] = {}
    mejor_puntaje = 0

    for indice, fila in enumerate(matriz[:max_filas]):
        mapeo = detectar_por_cabecera([str(valor) for valor in fila])
        puntaje = len(mapeo)
        if puntaje > mejor_puntaje:
            mejor_puntaje = puntaje
            mejor_indice = indice
            mejor_mapeo = mapeo

    if mejor_puntaje >= 2:
        return mejor_indice, mejor_mapeo
    return None, {}


def detectar_por_cabecera(encabezados: list[str]) -> dict[str, int]:
    """Mapea columnas usando sinónimos de cabecera."""
    normalizados = [normalizar_encabezado(encabezado) for encabezado in encabezados]
    mapeo: dict[str, int] = {}
    usados: set[int] = set()

    # "Fecha y hora" combinadas tienen prioridad.
    for indice, encabezado in enumerate(normalizados):
        if "fecha" in encabezado and "hora" in encabezado:
            if "fecha_hora" not in mapeo:
                mapeo["fecha_hora"] = indice
                usados.add(indice)
            break

    for indice, encabezado in enumerate(normalizados):
        if not encabezado or indice in usados:
            continue
        campo = _SINONIMO_A_CAMPO.get(encabezado)
        if campo is None:
            continue
        libre = _campo_libre(campo, mapeo)
        if libre:
            mapeo[libre] = indice
            usados.add(indice)

    for indice, encabezado in enumerate(normalizados):
        if not encabezado or indice in usados:
            continue
        for campo, frases in SINONIMOS.items():
            if campo in SOLO_EXACTO or campo in mapeo:
                continue
            if any(frase in encabezado for frase in frases):
                libre = _campo_libre(campo, mapeo)
                if libre:
                    mapeo[libre] = indice
                    usados.add(indice)
                    break

    return mapeo


@dataclass
class Perfil:
    """Resumen estadístico de una columna para inferir su contenido."""

    indice: int
    total: int = 0
    no_vacios: int = 0
    distintos: int = 0
    telefonos: int = 0
    fechas: int = 0
    fechas_texto: int = 0
    horas: int = 0
    horas_texto: int = 0
    duraciones: int = 0
    sentidos: int = 0
    tipos: int = 0
    imeis: int = 0
    numeros: list[float] = field(default_factory=list)
    textos: set[str] = field(default_factory=set)

    def ratio(self, atributo: str) -> float:
        return getattr(self, atributo) / self.no_vacios if self.no_vacios else 0.0

    @property
    def ratio_distintos(self) -> float:
        return self.distintos / self.no_vacios if self.no_vacios else 0.0


_RE_FECHA_TEXTO = re.compile(r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$")
_RE_FECHA_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}")
_RE_HORA_TEXTO = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?$")


def _es_fecha_texto(valor: object) -> bool:
    if isinstance(valor, (datetime, date)):
        return True
    crudo = norm.texto(valor)
    if not crudo:
        return False
    if _RE_FECHA_TEXTO.match(crudo) or _RE_FECHA_ISO.match(crudo):
        return True
    if re.fullmatch(r"\d{8}", crudo):
        return 1900 <= int(crudo[:4]) <= 2100
    return False


def _es_hora_texto(valor: object) -> bool:
    if isinstance(valor, time):
        return True
    if isinstance(valor, datetime):
        return True
    crudo = norm.texto(valor)
    return bool(crudo and _RE_HORA_TEXTO.match(crudo))


def perfilar_columna(valores: list[object], indice: int) -> Perfil:
    perfil = Perfil(indice=indice, total=len(valores))
    for valor in valores:
        crudo = norm.texto(valor)
        if not crudo:
            continue
        perfil.no_vacios += 1
        perfil.textos.add(crudo.lower())
        if norm.normalizar_telefono(crudo):
            perfil.telefonos += 1
        if _es_fecha_texto(valor):
            perfil.fechas += 1
            perfil.fechas_texto += 1
        elif re.fullmatch(r"\d{5}", crudo) and 20000 <= int(crudo) <= 60000:
            perfil.fechas += 1
        if _es_hora_texto(valor):
            perfil.horas += 1
            perfil.horas_texto += 1
        elif re.fullmatch(r"\d{5,6}", crudo) and norm.normalizar_hora(crudo):
            perfil.horas += 1
        if re.fullmatch(r"\d+", crudo) and 0 <= int(crudo) <= 86_400:
            perfil.duraciones += 1
        if norm.normalizar_sentido(crudo) in {"Entrante", "Saliente"}:
            perfil.sentidos += 1
        if norm.normalizar_tipo(crudo) in {"Voz", "SMS", "MMS", "Datos", "USSD"}:
            perfil.tipos += 1
        if norm.es_imei_valido(crudo):
            perfil.imeis += 1
        try:
            perfil.numeros.append(float(crudo.replace(",", ".")))
        except ValueError:
            pass
    perfil.distintos = len(perfil.textos)
    return perfil


def _columnas_iguales(a: Perfil, b: Perfil) -> bool:
    """Heurística para descartar columnas réplica (mismos valores)."""
    if not a.textos or not b.textos:
        return False
    interseccion = len(a.textos & b.textos)
    return interseccion / max(len(a.textos), len(b.textos)) >= 0.95


def _es_entero(valores: list[float]) -> bool:
    return bool(valores) and all(float(valor).is_integer() for valor in valores)


def _rango(valores: list[float]) -> tuple[float, float]:
    return (min(valores), max(valores)) if valores else (0.0, 0.0)


def detectar_por_valores(matriz: list[list[str]]) -> dict[str, int]:
    """Infiere el mapeo escaneando el contenido de cada columna."""
    if not matriz:
        return {}
    numero_columnas = max(len(fila) for fila in matriz)
    muestra = matriz[:500]
    columnas = [
        [fila[indice] if indice < len(fila) else "" for fila in muestra]
        for indice in range(numero_columnas)
    ]
    perfiles = [perfilar_columna(columna, indice) for indice, columna in enumerate(columnas)]
    mapeo: dict[str, int] = {}
    usados: set[int] = set()

    def asignar(campo: str, indice: int) -> None:
        mapeo[campo] = indice
        usados.add(indice)

    for perfil in perfiles:
        if perfil.no_vacios and perfil.ratio("sentidos") >= 0.8 and perfil.distintos <= 10:
            asignar("sentido", perfil.indice)
            break

    for perfil in perfiles:
        if perfil.indice in usados or not perfil.no_vacios:
            continue
        if perfil.ratio("tipos") >= 0.8 and perfil.distintos <= 10:
            asignar("tipo", perfil.indice)
            break

    for perfil in perfiles:
        if perfil.indice in usados or not perfil.no_vacios:
            continue
        if perfil.ratio("imeis") >= 0.8:
            asignar("imei", perfil.indice)
            break

    candidatas_fecha = [
        perfil
        for perfil in perfiles
        if perfil.indice not in usados and perfil.ratio("fechas_texto") >= 0.8
    ]
    if not candidatas_fecha:
        candidatas_fecha = [
            perfil
            for perfil in perfiles
            if perfil.indice not in usados
            and perfil.ratio("fechas") >= 0.8
            and perfil.numeros
            and all(20000 <= valor <= 60000 for valor in perfil.numeros)
        ]
    if candidatas_fecha:
        asignar("fecha", candidatas_fecha[0].indice)

    candidatas_hora = [
        perfil
        for perfil in perfiles
        if perfil.indice not in usados and perfil.ratio("horas_texto") >= 0.8
    ]
    if not candidatas_hora:
        candidatas_hora = [
            perfil
            for perfil in perfiles
            if perfil.indice not in usados
            and perfil.ratio("horas") >= 0.8
            and perfil.numeros
            and all(0 <= valor <= 235959 for valor in perfil.numeros)
        ]
    if candidatas_hora:
        asignar("hora", candidatas_hora[0].indice)

    candidatas_telefono = [
        perfil
        for perfil in perfiles
        if perfil.indice not in usados and perfil.ratio("telefonos") >= 0.8
    ]
    candidatas_telefono.sort(key=lambda perfil: perfil.indice)
    unicas: list[Perfil] = []
    for perfil in candidatas_telefono:
        if any(_columnas_iguales(perfil, previa) for previa in unicas):
            continue
        unicas.append(perfil)

    if unicas:
        titular = min(unicas, key=lambda perfil: (perfil.ratio_distintos, perfil.indice))
        asignar("titular", titular.indice)
        resto = [perfil for perfil in unicas if perfil.indice != titular.indice]
        resto.sort(key=lambda perfil: perfil.indice)
        if resto:
            asignar("destino", resto[0].indice)
        if len(resto) > 1:
            asignar("origen", resto[1].indice)

    # Componentes de fecha (año/mes/día) si no hay una fecha completa.
    if "fecha" not in mapeo:
        candidatos_anio = [
            perfil
            for perfil in perfiles
            if perfil.indice not in usados
            and perfil.numeros
            and _es_entero(perfil.numeros)
            and all(1900 <= valor <= 2100 for valor in perfil.numeros)
        ]
        if candidatos_anio:
            asignar("anio", candidatos_anio[0].indice)

    # Duración: columna entera pequeña que no sea año/mes/día.
    for perfil in perfiles:
        if perfil.indice in usados or not perfil.numeros:
            continue
        if not _es_entero(perfil.numeros):
            continue
        minimo, maximo = _rango(perfil.numeros)
        if minimo < 0 or maximo > 86_400:
            continue
        if 1900 <= minimo and maximo <= 2100:
            continue
        if 1 <= minimo and maximo <= 12:
            continue
        if 1 <= minimo and maximo <= 31:
            continue
        asignar("duracion", perfil.indice)
        break

    # Coordenadas: columnas decimales en rango geográfico.
    for perfil in perfiles:
        if perfil.indice in usados or not perfil.numeros:
            continue
        minimo, maximo = _rango(perfil.numeros)
        if not _es_entero(perfil.numeros) and -90 <= minimo and maximo <= 90:
            asignar("latitud", perfil.indice)
            break
    for perfil in perfiles:
        if perfil.indice in usados or not perfil.numeros:
            continue
        minimo, maximo = _rango(perfil.numeros)
        if -180 <= minimo and maximo <= 180 and not (-90 <= minimo and maximo <= 90):
            asignar("longitud", perfil.indice)
            break

    return mapeo


def parsear_mapeo(texto: str) -> dict[str, int]:
    """Convierte ``"titular=0,origen=3,imei=17"`` en un mapeo validado."""
    resultado: dict[str, int] = {}
    for parte in texto.split(","):
        if not parte.strip():
            continue
        campo, separador, indice = parte.partition("=")
        campo = campo.strip()
        if not separador or campo not in CAMPOS:
            raise ValueError(f"Campo de mapeo desconocido: '{campo}'.")
        try:
            posicion = int(indice)
        except ValueError as exc:
            raise ValueError(f"Índice inválido para '{campo}': '{indice}'.") from exc
        if posicion < 0:
            raise ValueError(f"El índice de '{campo}' no puede ser negativo.")
        resultado[campo] = posicion
    if not resultado:
        raise ValueError("El mapeo manual está vacío.")
    return resultado
