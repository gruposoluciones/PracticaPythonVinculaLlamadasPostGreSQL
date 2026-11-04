"""Configuración común de pytest: añade ``src`` y la raíz al PYTHONPATH."""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent

for ruta in (RAIZ / "src", RAIZ):
    if str(ruta) not in sys.path:
        sys.path.insert(0, str(ruta))
