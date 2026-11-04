"""Normalización de valores provenientes de Excel y CSV.

Los archivos de origen llegan en formatos heterogéneos: teléfonos como número
en notación científica, fechas como ``YYYYMMDD`` o serial de Excel, horas como
``HHMMSS``, ``HH:MM:SS`` o fracción del día. Este módulo concentra esas reglas
para que el ETL y los tests compartan exactamente el mismo criterio.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation

_VACIOS = {"", "nan", "none", "nat", "null", "n/a", "#n/a", "-"}

_RE_ENTERO = re.compile(r"^[+-]?\d+$")
_RE_DECIMAL = re.compile(r"^[+-]?\d+[.,]\d+$")
_RE_CIENTIFICO = re.compile(r"^[+-]?\d+(?:[.,]\d+)?[eE][+-]?\d+$")
_RE_HORA_TEXTO = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")
_RE_SOLO_DIGITOS = re.compile(r"^\d{1,6}$")

_EPOCA_EXCEL = datetime(1899, 12, 30)


def texto(valor: object) -> str:
    """Convierte cualquier valor de celda en texto limpio ('' si está vacío)."""
    if valor is None:
        return ""
    if isinstance(valor, float) and valor != valor:  # NaN sin depender de pandas
        return ""
    if isinstance(valor, (datetime, date, time)):
        return str(valor).strip()
    resultado = str(valor).strip()
    return "" if resultado.lower() in _VACIOS else resultado


def normalizar_telefono(valor: object) -> str | None:
    """Devuelve solo dígitos, conservando el número completo.

    Acepta ``51977369934``, ``+51 977 369 934``, ``5.1977369934E10`` y
    ``51977369934.0``. Devuelve ``None`` si no parece un teléfono válido.
    """
    crudo = texto(valor)
    if not crudo:
        return None

    limpio = crudo.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

    if _RE_CIENTIFICO.match(limpio):
        try:
            limpio = f"{Decimal(limpio.replace(',', '.')):.0f}"
        except InvalidOperation:
            return None
    elif _RE_DECIMAL.match(limpio):
        entero, decimales = re.split(r"[.,]", limpio)
        if set(decimales) <= {"0"}:
            limpio = entero

    digitos = re.sub(r"\D", "", limpio)
    if not 8 <= len(digitos) <= 15:
        return None
    return digitos


def normalizar_fecha(valor: object) -> date | None:
    """Acepta ``YYYYMMDD``, ``DD/MM/YYYY``, ``YYYY-MM-DD`` o serial de Excel."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor

    crudo = texto(valor)
    if not crudo:
        return None

    if " " in crudo:  # "2018-11-13 00:00:00" producido por pandas
        crudo = crudo.split(" ", 1)[0]

    for formato in ("%Y%m%d", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y"):
        try:
            return datetime.strptime(crudo, formato).date()
        except ValueError:
            continue

    try:
        numero = float(crudo.replace(",", "."))
    except ValueError:
        return None

    # Serial de Excel (1 = 1900-01-01; se usa 1899-12-30 por el bug de 1900).
    # Se limita a 1900-2100 para no confundir horas HHMMSS con fechas.
    if 1 <= numero <= 73_415:
        return (_EPOCA_EXCEL + timedelta(days=numero)).date()
    return None


def normalizar_hora(valor: object) -> time | None:
    """Acepta ``HHMMSS``, ``H:MM``, ``HH:MM:SS``, ``time`` o fracción del día."""
    if isinstance(valor, time):
        return valor
    if isinstance(valor, datetime):
        return valor.time()

    crudo = texto(valor)
    if not crudo:
        return None

    if " " in crudo:
        crudo = crudo.rsplit(" ", 1)[-1].strip()
    elif "T" in crudo:
        crudo = crudo.split("T", 1)[-1].strip()

    coincidencia = _RE_HORA_TEXTO.match(crudo)
    if coincidencia:
        hora = int(coincidencia.group(1))
        minuto = int(coincidencia.group(2))
        segundo = int(coincidencia.group(3) or 0)
        return _construir_hora(hora, minuto, segundo)

    if _RE_SOLO_DIGITOS.match(crudo):
        relleno = crudo.zfill(6)
        return _construir_hora(int(relleno[0:2]), int(relleno[2:4]), int(relleno[4:6]))

    try:
        numero = float(crudo.replace(",", "."))
    except ValueError:
        return None

    if 0 <= numero < 1:
        total = round(numero * 86_400)
        if total >= 86_400:
            total = 0
        return _construir_hora(total // 3600, (total % 3600) // 60, total % 60)

    if 0 <= numero < 240_000 and float(numero).is_integer():
        entero = int(numero)
        relleno = str(entero).zfill(6)
        return _construir_hora(int(relleno[0:2]), int(relleno[2:4]), int(relleno[4:6]))
    return None


def _construir_hora(hora: int, minuto: int, segundo: int) -> time | None:
    if not (0 <= hora < 24 and 0 <= minuto < 60 and 0 <= segundo < 60):
        return None
    return time(hora, minuto, segundo)


def normalizar_duracion(valor: object) -> int | None:
    """Duración en segundos. Vacío queda como NULL; negativo o inválido, NULL."""
    crudo = texto(valor)
    if not crudo:
        return None
    crudo = crudo.replace(",", ".")
    try:
        numero = Decimal(crudo)
    except InvalidOperation:
        return None
    if numero < 0:
        return None
    return int(numero)


def normalizar_tipo(valor: object) -> str | None:
    """Normaliza el tipo de comunicación a ``Voz``, ``SMS``, ``MMS``, ``Datos``."""
    crudo = texto(valor)
    if not crudo:
        return None
    equivalencias = {
        "voz": "Voz",
        "llamada": "Voz",
        "voice": "Voz",
        "call": "Voz",
        "sms": "SMS",
        "mms": "MMS",
        "datos": "Datos",
        "data": "Datos",
        "internet": "Datos",
        "ussd": "USSD",
    }
    return equivalencias.get(crudo.lower(), crudo)


def normalizar_sentido(valor: object) -> str | None:
    """Normaliza el sentido a ``Entrante`` o ``Saliente``."""
    crudo = texto(valor)
    if not crudo:
        return None
    equivalencias = {
        "entrante": "Entrante",
        "in": "Entrante",
        "entrada": "Entrante",
        "recibida": "Entrante",
        "incoming": "Entrante",
        "mtc": "Entrante",
        "mt": "Entrante",
        "terminada": "Entrante",
        "saliente": "Saliente",
        "out": "Saliente",
        "salida": "Saliente",
        "enviada": "Saliente",
        "outgoing": "Saliente",
        "moc": "Saliente",
        "mo": "Saliente",
        "originada": "Saliente",
    }
    return equivalencias.get(crudo.lower(), crudo.title())


def _luhn_valido(digitos: str) -> bool:
    """Valida el dígito de control Luhn (usado por IMEI)."""
    if not digitos.isdigit():
        return False
    suma = 0
    for posicion, caracter in enumerate(reversed(digitos)):
        valor = int(caracter)
        if posicion % 2 == 1:
            valor *= 2
            if valor > 9:
                valor -= 9
        suma += valor
    return suma % 10 == 0


def normalizar_imei(valor: object) -> str | None:
    """IMEI/IMEISV: 14-16 dígitos.

    No se exige Luhn porque algunos exportadores no lo calculan; para inferir
    columnas se usa ``es_imei_valido``.
    """
    digitos = re.sub(r"\D", "", texto(valor))
    return digitos if 14 <= len(digitos) <= 16 else None


def es_imei_valido(valor: object) -> bool:
    """IMEI de 15 dígitos con dígito de control Luhn correcto."""
    digitos = normalizar_imei(valor)
    return bool(digitos and len(digitos) == 15 and _luhn_valido(digitos))


def normalizar_imsi(valor: object) -> str | None:
    """IMSI: 14-16 dígitos (MCC + MNC + MSIN)."""
    digitos = re.sub(r"\D", "", texto(valor))
    return digitos if 14 <= len(digitos) <= 16 else None


def normalizar_identificador(valor: object, maximo: int = 64) -> str | None:
    """Identificador técnico (celda, LAC, antena, operador...)."""
    crudo = texto(valor)
    if not crudo or len(crudo) > maximo:
        return None
    return crudo


def normalizar_coordenada(valor: object, limite: float) -> float | None:
    """Latitud (-90..90) o longitud (-180..180)."""
    crudo = texto(valor).replace(",", ".")
    if not crudo:
        return None
    try:
        numero = float(crudo)
    except ValueError:
        return None
    if not -limite <= numero <= limite:
        return None
    return numero


def normalizar_booleano(valor: object) -> bool | None:
    """Convierte valores de roaming a booleano; vacío o desconocido, NULL."""
    crudo = texto(valor).lower()
    if crudo in {"1", "si", "sí", "true", "yes", "y", "roaming"}:
        return True
    if crudo in {"0", "no", "false", "n"}:
        return False
    return None


def clasificar_telefono(numero: object, codigo_pais: str = "51") -> str | None:
    """Clasifica un número como ``movil``, ``fijo``, ``extranjero`` o NULL.

    Para Perú (código 51): móvil = 9 dígitos que empiezan por 9; fijo = 6-8
    dígitos nacionales. Cualquier número de 10+ dígitos que no empiece por el
    código de país se considera extranjero.
    """
    digitos = normalizar_telefono(numero)
    if not digitos:
        return None

    if codigo_pais and digitos.startswith(codigo_pais):
        nacional = digitos[len(codigo_pais) :]
        if len(nacional) == 9 and nacional.startswith("9"):
            return "movil"
        if 6 <= len(nacional) <= 8:
            return "fijo"
        if len(nacional) > 9 and nacional.startswith("9"):
            return "movil"
        return None

    if len(digitos) == 9 and digitos.startswith("9"):
        return "movil"
    if 6 <= len(digitos) <= 8:
        return "fijo"
    if len(digitos) >= 10:
        return "extranjero"
    return None


def calcular_hash_fila(
    titular: str,
    origen: str | None,
    destino: str | None,
    fecha: date | None,
    hora: time | None,
    duracion_seg: int | None,
    tipo: str | None,
    sentido: str | None,
    imei: str | None = None,
    celda: str | None = None,
    antena: str | None = None,
) -> str:
    """Hash estable de los campos clave para evitar duplicados al recargar.

    Los campos técnicos (IMEI/celda/antena) solo se incluyen cuando están
    presentes, para no invalidar los hashes de cargas anteriores.
    """
    partes = [
        titular,
        origen or "",
        destino or "",
        fecha.isoformat() if fecha else "",
        hora.isoformat() if hora else "",
        "" if duracion_seg is None else str(duracion_seg),
        tipo or "",
        sentido or "",
    ]
    if imei or celda or antena:
        partes.extend([imei or "", celda or "", antena or ""])
    return hashlib.sha256("|".join(partes).encode("utf-8")).hexdigest()


def enmascarar(numero: str | None) -> str:
    """Enmascara un teléfono para registros de log (``519****9934``)."""
    if not numero:
        return ""
    if len(numero) <= 7:
        return "*" * len(numero)
    return f"{numero[:3]}{'*' * (len(numero) - 7)}{numero[-4:]}"
