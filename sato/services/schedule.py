"""Calendario de sincronizacion (sin dependencias pesadas: lo usa tambien la API)."""

from __future__ import annotations

import datetime as dt
import os


def dia_sync() -> int:
    """Dia del mes de la sincronizacion (SATO_SYNC_DIA, por defecto 2), acotado a 1-28 para que exista en todos los meses."""
    try:
        return min(max(int(os.environ.get("SATO_SYNC_DIA", "2")), 1), 28)
    except ValueError:
        return 2


def proxima_sync(hoy: dt.date | None = None) -> dt.date:
    """Proxima fecha de sincronizacion mensual."""
    hoy = hoy or dt.date.today()
    dia = dia_sync()
    cand = hoy.replace(day=dia)
    if cand <= hoy:
        cand = (hoy.replace(day=1) + dt.timedelta(days=32)).replace(day=dia)
    return cand
