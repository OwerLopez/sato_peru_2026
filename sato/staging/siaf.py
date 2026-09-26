"""Staging de la ejecucion presupuestal SIAF (MEF, Consulta Amigable).

Fuente: https://datosabiertos.mef.gob.pe/dataset/presupuesto-y-ejecucion-de-gasto
Cada anio se publica como un zip con un CSV de 7-10 GB a nivel de
anio-mes x ejecutora x meta x fuente x clasificador de gasto.

Se agrega a nivel PROYECTO (TIPO_ACT_PROY = 2, PRODUCTO_PROYECTO = CUI) x
anio x mes, conservando los montos de las fases del gasto. El resultado
es pequenio y cubre todo el pais, lo que permite construir la serie
financiera mensual de cualquier inversion.

Semantica (verificada empiricamente, ver docs/research/EVIDENCE_LOG.md E6):
  * MES_EJE 1..12: devengado / girado / comprometido son FLUJOS del mes.
  * MES_EJE 0: contiene PIA y PIM del anio. El PIM es el valor VIGENTE a la
    fecha de generacion del archivo (anio en curso) o el final del anio
    (anios cerrados); NO esta fechado. Por tanto el PIM del anio en curso no
    puede usarse como feature en T < fin de anio (leakage). El PIA si, porque
    se conoce desde el 1 de enero.
"""

from __future__ import annotations

import logging
import subprocess
import zipfile
from pathlib import Path

import duckdb

from sato.config import RAW, STAGING

log = logging.getLogger(__name__)

AMOUNTS = [
    "MONTO_PIA",
    "MONTO_PIM",
    "MONTO_CERTIFICADO",
    "MONTO_COMPROMETIDO_ANUAL",
    "MONTO_COMPROMETIDO",
    "MONTO_DEVENGADO",
    "MONTO_GIRADO",
]


def stage_year(zip_path: Path, out_dir: Path = STAGING / "siaf", keep_csv: bool = False) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / (zip_path.stem.split("-")[0] + ".parquet")
    if out.exists():
        log.info("ya existe %s", out)
        return out
    with zipfile.ZipFile(zip_path) as z:
        name = z.namelist()[0]
        csv_path = zip_path.parent / name
        if not csv_path.exists():
            log.info("descomprimiendo %s", name)
            # unzip del sistema es mas rapido que zipfile para 10 GB
            subprocess.run(["unzip", "-o", "-q", str(zip_path), "-d", str(zip_path.parent)], check=True)
    sums = ",\n".join(f"sum(try_cast({a} as double)) as {a.lower()}" for a in AMOUNTS)
    sql = f"""
    copy (
      select try_cast(ANO_EJE as int) as anio,
             try_cast(MES_EJE as int) as mes,
             PRODUCTO_PROYECTO as cui,
             any_value(PRODUCTO_PROYECTO_NOMBRE) as nombre_proyecto,
             string_agg(distinct DEPARTAMENTO_META_NOMBRE, '|') as departamentos_meta,
             string_agg(distinct NIVEL_GOBIERNO, '|') as niveles,
             string_agg(distinct SEC_EJEC, '|') as sec_ejec,
             string_agg(distinct FUNCION_NOMBRE, '|') as funciones,
             {sums}
      from read_csv('{csv_path.as_posix()}', header=true, all_varchar=true, parallel=true)
      where TIPO_ACT_PROY = '2'
      group by all
    ) to '{out.as_posix()}' (format parquet, compression zstd)
    """
    con = duckdb.connect()
    con.sql("set preserve_insertion_order=false")
    con.sql(sql)
    n = con.sql(f"select count(*), count(distinct cui) from '{out.as_posix()}'").fetchone()
    log.info("%s -> %s filas, %s CUI", zip_path.name, n[0], n[1])
    if not keep_csv:
        csv_path.unlink()
    return out


def stage_all(raw_dir: Path = RAW / "mef" / "siaf") -> list[Path]:
    return [stage_year(z) for z in sorted(raw_dir.glob("*.zip"))]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    stage_all()
