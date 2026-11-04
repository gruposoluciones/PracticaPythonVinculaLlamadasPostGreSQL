"""Configuración central del proyecto basada en variables de entorno.

No debe contener credenciales por defecto: la contraseña de PostgreSQL se lee
siempre de ``DB_PASSWORD`` (archivo ``.env`` local, nunca versionado).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent

# Carga .env si existe (silencioso si no existe).
load_dotenv(RAIZ / ".env")


class ConfiguracionInvalida(RuntimeError):
    """Falta una variable de entorno obligatoria."""


@dataclass(frozen=True)
class Settings:
    """Parámetros de ejecución de la aplicación."""

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "comunicaciones"
    db_user: str = "postgres"
    db_password: str = ""
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    max_filas: int = 500
    max_subida_mb: int = 25
    directorio_entrada: Path = field(default=RAIZ / "data" / "entrada")
    directorio_procesados: Path = field(default=RAIZ / "data" / "procesados")
    directorio_web: Path = field(default=RAIZ / "web")

    @property
    def dsn(self) -> dict[str, object]:
        """Parámetros de conexión para ``psycopg2.connect``."""
        return {
            "host": self.db_host,
            "port": self.db_port,
            "dbname": self.db_name,
            "user": self.db_user,
            "password": self.db_password,
            "connect_timeout": 10,
        }


def _entero(nombre: str, defecto: int) -> int:
    valor = os.getenv(nombre)
    if not valor:
        return defecto
    try:
        return int(valor)
    except ValueError as exc:  # pragma: no cover - configuración inválida
        raise ConfiguracionInvalida(f"{nombre} debe ser un número entero") from exc


@lru_cache(maxsize=1)
def obtener_settings() -> Settings:
    """Devuelve la configuración, validando lo imprescindible."""
    password = os.getenv("DB_PASSWORD", "")
    if not password:
        raise ConfiguracionInvalida(
            "Falta DB_PASSWORD. Copia .env.example a .env y define la contraseña."
        )

    return Settings(
        db_host=os.getenv("DB_HOST", "localhost"),
        db_port=_entero("DB_PORT", 5432),
        db_name=os.getenv("DB_NAME", "comunicaciones"),
        db_user=os.getenv("DB_USER", "postgres"),
        db_password=password,
        api_host=os.getenv("API_HOST", "127.0.0.1"),
        api_port=_entero("API_PORT", 8000),
        max_filas=_entero("MAX_FILAS", 500),
        max_subida_mb=_entero("MAX_SUBIDA_MB", 25),
    )
