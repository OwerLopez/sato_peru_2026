"""Staging de datasets de Inversion Publica del MEF (Banco de Inversiones / Invierte.pe).

Fuente: https://datosabiertos.mef.gob.pe (categoria "inversion-publica").
Los archivos se regeneran a diario en fs.datosabiertos.mef.gob.pe; por eso cada
descarga se versiona por fecha en `data/raw/mef/` y el staging registra la
fecha de corte (`fecha_corte`) para trazabilidad.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import duckdb

from sato.config import RAW, STAGING

log = logging.getLogger(__name__)

CSV = "header=true, all_varchar=true"


def _q(path: Path) -> str:
    return path.as_posix()


def stage_inversiones(raw: Path = RAW / "mef", out: Path = STAGING, fecha_corte: str | None = None) -> Path:
    """Universo de inversiones: ACTIVAS (detalle) + CERRADAS + DESACTIVADAS.

    Una inversion puede figurar en mas de un archivo (p.ej. cerrada y luego
    reactivada); se conserva una fila por CUI con prioridad ACTIVO > CERRADO >
    DESACTIVADO y se registra en `fuentes` todas las apariciones.
    """
    fecha_corte = fecha_corte or date.today().isoformat()
    dst = out / "mef_inversiones.parquet"
    con = duckdb.connect()
    con.sql(
        f"""
        create table u as
        select 'ACTIVO' fuente, 1 prio, NIVEL nivel, SECTOR sector, ENTIDAD entidad, CODIGO_UNICO cui,
               CODIGO_SNIP snip, NOMBRE_INVERSION nombre, ESTADO estado, SITUACION situacion,
               try_cast(MONTO_VIABLE as double) monto_viable, try_cast(COSTO_ACTUALIZADO as double) costo_actualizado,
               try_cast(MONTO_LAUDO as double) monto_laudo, try_cast(FECHA_REGISTRO as date) fecha_registro,
               try_cast(FECHA_VIABILIDAD as date) fecha_viabilidad, FUNCION funcion, PROGRAMA programa,
               SUBPROGRAMA subprograma, MARCO marco, TIPO_INVERSION tipo_inversion, DES_MODALIDAD modalidad,
               DES_TIPOLOGIA tipologia, NOMBRE_UEI uei, SEC_EJEC sec_ejec, NOMBRE_UEP uep,
               DEPARTAMENTO departamento, PROVINCIA provincia, DISTRITO distrito, lpad(UBIGEO, 6, '0') ubigeo,
               try_cast(LATITUD as double) latitud, try_cast(LONGITUD as double) longitud,
               try_cast(FEC_INI_EJECUCION as date) f08_ini_ejecucion, try_cast(FEC_FIN_EJECUCION as date) f08_fin_ejecucion,
               try_cast(FEC_INI_EJEC_FISICA as date) f12b_ini_ejec_fisica, try_cast(FEC_FIN_EJEC_FISICA as date) f12b_fin_ejec_fisica,
               try_cast(AVANCE_FISICO as double) avance_fisico, try_cast(AVANCE_EJECUCION as double) avance_ejecucion,
               PRIMER_DEVENGADO primer_devengado, ULTIMO_DEVENGADO ultimo_devengado,
               null::date fecha_cierre
        from read_csv('{_q(raw / "DETALLE_INVERSIONES.csv")}', {CSV})
        union all
        select 'CERRADO', 2, NIVEL, SECTOR, ENTIDAD, CODIGO_UNICO, CODIGO_SNIP, NOMBRE_INVERSION, ESTADO, SITUACION,
               try_cast(MONTO_VIABLE as double), try_cast(COSTO_ACTUALIZADO as double), try_cast(MONTO_LAUDO as double),
               try_cast(FECHA_REGISTRO as date), try_cast(FECHA_VIABILIDAD as date), FUNCION, PROGRAMA, SUBPROGRAMA,
               MARCO, TIPO_INVERSION, DES_MODALIDAD, DES_TIPOLOGIA, NOM_UEI, SEC_EJEC, NOM_UEP,
               DEPARTAMENTO, PROVINCIA, DISTRITO, lpad(UBIGEO, 6, '0'), try_cast(LATITUD as double), try_cast(LONGITUD as double),
               null, null, try_cast(INICIO_EJEC_FISICA as date), try_cast(CULMINA_EJEC_FISICA as date),
               null, null, PRIMER_DEVENGADO, ULTIMO_DEVENGADO, try_cast(FEC_CIERRE as date)
        from read_csv('{_q(raw / "CIERRE_INVERSIONES.csv")}', {CSV})
        union all
        select 'DESACTIVADO', 3, NIVEL, SECTOR, ENTIDAD, CODIGO_UNICO, COD_SNIP, NOMBRE_INVERSION, ESTADO, SITUACION,
               try_cast(MONTO_VIABLE as double), try_cast(COSTO_ACTUALIZADO as double), try_cast(MONTO_LAUDO as double),
               try_cast(FECHA_REGISTRO as date), try_cast(FECHA_VIABILIDAD as date), FUNCION, PROGRAMA, SUBPROGRAM,
               MARCO, TIPO_INVERSION, DES_MODALIDAD, DES_TIPOLOGIA, NOM_UEI, null, NOM_UEP,
               DEPARTAMENTO, PROVINCIA, DISTRITO, lpad(UBIGEO, 6, '0'), try_cast(LATITUD as double), try_cast(LONGITUD as double),
               null, null, null, null, null, null, null, null, null
        from read_csv('{_q(raw / "INVERSIONES_DESACTIVADAS.csv")}', {CSV})
        """
    )
    con.sql(
        f"""
        copy (
          select * exclude (prio, rn), '{fecha_corte}'::date fecha_corte
          from (select *, row_number() over (partition by cui order by prio) rn,
                       string_agg(fuente, '|') over (partition by cui) fuentes
                from u where cui is not null and cui <> '')
          where rn = 1
        ) to '{_q(dst)}' (format parquet, compression zstd)
        """
    )
    log.info("inversiones: %s", con.sql(f"select fuente, count(*) from '{_q(dst)}' group by 1").fetchall())
    return dst


def stage_estado_situacional(raw: Path = RAW / "mef", out: Path = STAGING) -> Path:
    """Registros fechados de situacion / problematica / riesgos (F12B)."""
    dst = out / "mef_estado_situacional.parquet"
    con = duckdb.connect()
    con.sql(
        f"""
        copy (
          select CODIGO_UNICO cui, DESCRIPCION descripcion, try_cast(COD_TIPO as int) cod_tipo,
                 TIP_REGISTRO tipo_registro,
                 try_cast(try_cast(PERIODO as double) as int) periodo,
                 try_cast(FECHA_REGISTRO as timestamp) fecha_registro
          from read_csv('{_q(raw / "ESTADO_SITUACIONAL.csv")}', {CSV})
        ) to '{_q(dst)}' (format parquet, compression zstd)
        """
    )
    return dst


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    stage_inversiones()
    stage_estado_situacional()
