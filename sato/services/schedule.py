"""Calendario de sincronizacion (sin dependencias pesadas: lo usa tambien la API)."""

from __future__ import annotations

import datetime as dt
import os


def proxima_sync(hoy: dt.date | None = None) -> dt.date:
    """Proxima fecha de sincronizacion mensual (dia SATO_SYNC_DIA de cada mes; por defecto el 2)."""
    hoy = hoy or dt.date.today()
    dia = int(os.environ.get("SATO_SYNC_DIA", "2"))
    cand = hoy.replace(day=dia)
    if cand <= hoy:
        cand = (hoy.replace(day=1) + dt.timedelta(days=32)).replace(day=dia)
    return cand
