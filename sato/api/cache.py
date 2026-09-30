"""Cache en memoria de respuestas agregadas, invalidada automaticamente cuando se carga un nuevo corte de datos.

Los datos de la plataforma solo cambian con cada carga (mensual); las consultas agregadas (panorama, comparador,
calibracion, mapas) se recalculan una vez por version de datos y por combinacion de parametros. La version se lee
de `corte_datos.generado_en` (cambia en cada carga) como maximo cada 15 s. Cada worker de Uvicorn tiene su cache.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from functools import wraps

from sqlalchemy.exc import OperationalError

from sato.api import db
from sato.api.settings import get_settings

_lock = threading.Lock()
_store: OrderedDict = OrderedDict()
_version: dict = {"t": -1e9, "v": None}
MAX_ENTRADAS = 512
stats = {"aciertos": 0, "fallos": 0}


def version_datos() -> str:
    now = time.monotonic()
    if now - _version["t"] > 15:
        try:
            r = db.one("select max(generado_en)::text v from corte_datos")
            _version.update(t=now, v=(r or {}).get("v"))
        except OperationalError:
            if _version["v"] is None:
                raise
            # base momentaneamente no disponible: se siguen sirviendo las respuestas de la version conocida
            _version["t"] = now
    return str(_version["v"])


def limpiar() -> None:
    with _lock:
        _store.clear()
        _version.update(t=-1e9, v=None)


def cacheado(fn):
    @wraps(fn)
    def envoltura(*args, **kwargs):
        clave = (fn.__module__, fn.__name__, args, tuple(sorted(kwargs.items())), version_datos())
        ttl = get_settings().cache_segundos
        with _lock:
            hit = _store.get(clave)
            if hit and time.monotonic() - hit[0] < ttl:
                _store.move_to_end(clave)
                stats["aciertos"] += 1
                return hit[1]
        valor = fn(*args, **kwargs)
        with _lock:
            stats["fallos"] += 1
            _store[clave] = (time.monotonic(), valor)
            while len(_store) > MAX_ENTRADAS:
                _store.popitem(last=False)
        return valor

    return envoltura
