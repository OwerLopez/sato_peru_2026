"""Extraccion de informacion (NLP basado en reglas) desde el texto de los asientos.

Extrae de cada asiento, cuando esta presente:
  * avance fisico ACUMULADO EJECUTADO (%)   -> `ie_ejec`
  * avance fisico ACUMULADO PROGRAMADO (%)  -> `ie_prog`
  * estado declarado ("atrasada"/"adelantada") y su magnitud -> `ie_estado`, `ie_brecha`

La precision del extractor se valida contra el dataset oficial de
Valorizaciones de OECE (avance programado/ejecutado registrado por la
entidad) en `research/validate_extraction.py`.

Features por (cuaderno, T) usando solo asientos con fecha <= T:
  ie_ratio_ultimo       : ejec/prog del ultimo asiento (<= T, ventana 90 d) con ambos valores
  ie_ratio_min_90d      : minimo ejec/prog en la ventana
  ie_brecha_ultima      : ejec - prog (puntos porcentuales) del ultimo reporte
  ie_n_atrasada_60d     : asientos en 60 d que declaran la obra "atrasada/retrasada" en X %
  ie_n_adelantada_60d   : idem "adelantada"
  ie_dias_desde_reporte : dias desde el ultimo reporte de avance extraido
"""

from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path

import duckdb
import pandas as pd

from sato.config import CURATED, FEATURES

log = logging.getLogger(__name__)

NUM = r"(?<![\d.,])(\d{1,3}(?:[.,]\d{1,4})?)\s*%"
# Entre la etiqueta y el porcentaje se toleran fechas ("al 30.06.2025 :") y montos
# ("1,115,374.91 (") pero no otro signo %, ni la mencion de la regla del 80%.
GAP = r"[^%]{0,45}?"
RX_EJEC = [
    re.compile(r"(?:avance\s+)?(?:fisico\s+)?(?:ejecutado|real|valorizado)\s+acumulado" + GAP + NUM),
    re.compile(r"acumulado\s+(?:ejecutado|real|valorizado)" + GAP + NUM),
    re.compile(r"avance\s+(?:fisico\s+)?(?:ejecutado|real)\s*[:=]" + GAP + NUM),
    re.compile(r"avance\s+(?:fisico\s+)?acumulado(?!\s+programado)[^%]{0,25}?" + NUM),
]
RX_PROG = [
    re.compile(r"programado\s+acumulado" + GAP + NUM),
    re.compile(r"acumulado\s+programado" + GAP + NUM),
    re.compile(r"avance\s+(?:fisico\s+)?programado\s*[:=]" + GAP + NUM),
    re.compile(r"(?:frente|respecto)\s+(?:al|a un)\s+" + NUM + r"\s+programado"),
    re.compile(r"(?:un|el)\s+programado\s+(?:acumulado\s+)?(?:de|del)?\s*" + NUM),
]
RX_ESTADO = re.compile(r"(atrasad[ao]|retrasad[ao]|adelantad[ao])\s+(?:en\s+(?:un\s+)?)?" + NUM)
RX_REGLA80 = re.compile(r"(menor|debajo|inferior|menos)\s+(?:al|del|de)\s+(?:el\s+)?80\s*%|80\s*%\s+del\s+(?:monto|avance|calendario|valoriz)")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s)


def _num(x: str) -> float:
    return float(x.replace(",", "."))


def _first(rxs, t):
    for rx in rxs:
        m = rx.search(t)
        if m:
            v = _num(m.group(1))
            if 0 <= v <= 150:
                return v
    return None


def extract(text: str) -> tuple:
    t = _norm(text)
    if "%" not in t:
        return (None, None, None, None)
    t = RX_REGLA80.sub(" [regla80] ", t)  # no confundir la regla normativa con un avance reportado
    ejec, prog = _first(RX_EJEC, t), _first(RX_PROG, t)
    m = RX_ESTADO.search(t)
    estado = brecha = None
    if m:
        estado = "atrasada" if m.group(1).startswith(("atras", "retras")) else "adelantada"
        brecha = _num(m.group(2)) * (-1 if estado == "atrasada" else 1)
    return (ejec, prog, estado, brecha)


def extract_all(out: Path = FEATURES) -> Path:
    con = duckdb.connect()
    asi = con.sql(
        f"""select cuaderno_id, fecha::timestamp fecha, tipo_std, coalesce(titulo,'') || ' . ' || coalesce(descripcion,'') txt
            from '{(CURATED / 'asiento.parquet').as_posix()}' where instr(coalesce(titulo, '') || coalesce(descripcion, ''), '%') > 0"""
    ).df()
    vals = [extract(t) for t in asi["txt"]]
    ie = pd.DataFrame(vals, columns=["ie_ejec", "ie_prog", "ie_estado", "ie_brecha"], index=asi.index)
    asi = pd.concat([asi.drop(columns="txt"), ie], axis=1)
    asi = asi[ie.notna().any(axis=1)]
    dst = out / "asiento_extraccion.parquet"
    asi.to_parquet(dst, index=False)
    log.info("extraccion: %s asientos con algun valor", len(asi))
    return dst


def build_features(out: Path = FEATURES) -> Path:
    con = duckdb.connect()
    con.sql(f"create table panel as select cuaderno_id, \"T\"::date t from '{(out / 'panel.parquet').as_posix()}'")
    con.sql(
        f"""create table ie as select cuaderno_id, fecha::date fecha, ie_ejec, ie_prog, ie_estado, ie_brecha,
                   case when ie_prog > 0 and ie_ejec is not null then ie_ejec / ie_prog end ratio
            from '{(out / 'asiento_extraccion.parquet').as_posix()}'"""
    )
    df = con.sql(
        """
        select p.cuaderno_id, p.t as "T",
          arg_max(i.ratio, i.fecha) filter (where i.ratio is not null and i.fecha > p.t - 90) as ie_ratio_ultimo,
          min(i.ratio) filter (where i.fecha > p.t - 90) as ie_ratio_min_90d,
          arg_max(i.ie_ejec - i.ie_prog, i.fecha) filter (where i.ratio is not null and i.fecha > p.t - 90) as ie_brecha_ultima,
          count(*) filter (where i.ie_estado = 'atrasada' and i.fecha > p.t - 60) as ie_n_atrasada_60d,
          count(*) filter (where i.ie_estado = 'adelantada' and i.fecha > p.t - 60) as ie_n_adelantada_60d,
          p.t - max(i.fecha) filter (where i.ie_ejec is not null or i.ie_prog is not null) as ie_dias_desde_reporte
        from panel p join ie i on i.cuaderno_id = p.cuaderno_id and i.fecha <= p.t
        group by p.cuaderno_id, p.t
        """
    ).df()
    df["T"] = pd.to_datetime(df["T"])
    df["ie_dias_desde_reporte"] = pd.to_numeric(df["ie_dias_desde_reporte"], errors="coerce")
    dst = out / "features_text_ie.parquet"
    df.to_parquet(dst, index=False)
    log.info("features IE: %s", df.shape)
    return dst


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    extract_all()
    build_features()
