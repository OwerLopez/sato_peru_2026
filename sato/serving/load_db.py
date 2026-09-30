"""Carga idempotente de la base de datos de la plataforma (PostgreSQL).

    DATABASE_URL=postgresql://... python -m sato.serving.load_db

1. Aplica migraciones SQL pendientes (db/migrations/*.sql, tabla schema_migrations).
2. Valida las entradas (archivos presentes, columnas requeridas, claves sin nulos ni duplicados).
3. En UNA transaccion: borra con DELETE las tablas de datos (la API sigue leyendo los datos vigentes hasta el COMMIT) y las recarga desde data/curated,
   data/staging, artifacts/release y artifacts/cartera, con ALCANCE NACIONAL (todos los
   departamentos). Usuarios, revisiones, suscripciones, sincronizaciones y auditoria no se tocan.
4. Registra el corte de datos, el linaje (manifest.jsonl) y la conciliacion de registros por tabla
   (filas de origen, cargadas y descartadas con su motivo).
5. Compuerta de integridad ANTES de confirmar: chequeos criticos de `calidad` y caida maxima de filas
   de las tablas clave frente a la carga vigente (SATO_CARGA_CAIDA_MAX, 0.2 por defecto).
Si algo falla o la compuerta rechaza la carga, la transaccion se revierte y la base queda como estaba.
Cada intento queda en la tabla `carga_datos` (OK, RECHAZADA o ERROR) con su validacion y conciliacion.
SATO_CARGA_FORZAR=1 acepta una caida de filas revisada manualmente (queda registrado); nunca omite los chequeos criticos.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg

from sato.config import ARTIFACTS, CURATED, RAW, ROOT, STAGING
from sato.serving.lenguaje import GRUPOS_CLAROS, categoria, etiqueta, factor_cartera, factor_cuaderno
from sato.serving.texto_es import acentuar

log = logging.getLogger(__name__)
MIGRATIONS = ROOT / "db" / "migrations"
DATA_TABLES = ["simulacion", "cartera_explicacion", "cartera_riesgo", "cartera_obra", "configuracion",
               "evidencia", "explicacion", "prediccion", "modelo", "asiento", "obra", "inversion", "entidad", "contratista",
               "siaf_mensual", "infobras_obra", "contraloria_paralizada", "mef_seguimiento", "experimento_resultado",
               "comparacion_ab", "fuente_archivo", "corte_datos"]


# tablas cuya caida brusca de filas indica una fuente incompleta o un paso previo fallido
TABLAS_CLAVE = ("obra", "asiento", "prediccion", "explicacion", "inversion", "siaf_mensual", "infobras_obra", "cartera_obra", "cartera_riesgo")
# entradas de la carga: (columnas requeridas, clave que no puede tener nulos ni duplicados)
ENTRADAS = {
    "cuaderno": (["cuaderno_id", "tiene_metadatos", "denominacion", "ruc_entidad", "departamento", "cui", "primer_asiento", "ultimo_asiento",
                  "n_asientos", "f_valorizacion_menor_80", "f_calendario_acelerado"], "cuaderno_id"),
    "mef_inversiones": (["cui", "nombre", "funcion", "monto_viable", "departamento", "latitud", "longitud"], "cui"),
    "infobras_obras": (["codigo_infobras", "codigo_unico_de_inversion", "nombre_de_obra", "plazo_de_ejecucion_en_dias"], None),
    "seace_contratos": (["n_cod_contrato", "urlcontrato"], None),
    "predicciones": (["cuaderno_id", "T", "tipo", "score", "percentil", "nivel", "alerta", "y_observado"], None),
    "cartera_obras": (["codigo_infobras", "codigo_unico_de_inversion", "estado_operativo", "y_30"], "codigo_infobras"),
}


class CargaRechazada(RuntimeError):
    """La compuerta de integridad rechazo la carga: la base conserva los datos anteriores."""


def dsn() -> str:
    url = os.environ.get("DATABASE_URL", "postgresql://sato:sato@127.0.0.1:5432/sato")
    return url.replace("postgresql+psycopg://", "postgresql://")


def validar_entradas(frames: dict[str, pd.DataFrame | None]) -> list[str]:
    """Hallazgos que impiden cargar: archivo ausente o vacio, columnas faltantes, claves nulas o duplicadas."""
    fallas = []
    for nombre, (cols, clave) in ENTRADAS.items():
        df = frames.get(nombre)
        if df is None:
            if nombre != "cartera_obras":  # la cartera INFOBRAS es opcional (versiones sin modelo de cartera)
                fallas.append(f"{nombre}: archivo ausente")
            continue
        if df.empty:
            fallas.append(f"{nombre}: archivo sin filas")
            continue
        faltan = [c for c in cols if c not in df.columns]
        if faltan:
            fallas.append(f"{nombre}: faltan columnas {faltan}")
        if clave and clave in df.columns:
            if n := int(df[clave].isna().sum()):
                fallas.append(f"{nombre}: {n} filas sin {clave}")
            if n := int(df[clave].dropna().duplicated().sum()):
                fallas.append(f"{nombre}: {n} valores repetidos de {clave}")
    return fallas


def compuerta(previos: dict[str, int], nuevos: dict[str, int], max_caida: float) -> list[str]:
    """Rechaza la carga si una tabla clave queda vacia o pierde mas de `max_caida` de sus filas frente a la carga vigente."""
    fallas = []
    for t in TABLAS_CLAVE:
        a, b = previos.get(t, 0), nuevos.get(t, 0)
        if b == 0 and t not in ("cartera_obra", "cartera_riesgo"):
            fallas.append(f"{t}: la carga dejaria la tabla vacia")
        elif a > 0 and b < (1 - max_caida) * a:
            fallas.append(f"{t}: {b:,} filas frente a {a:,} de la carga vigente (caida de {1 - b / a:.0%}; maximo permitido {max_caida:.0%})")
    return fallas


def conteos(conn: psycopg.Connection) -> dict[str, int]:
    return {t: conn.execute(f"select count(*) from sato.{t}").fetchone()[0] for t in DATA_TABLES}


def _registro(sql: str, params: tuple) -> int | None:
    """Historial de cargas en una conexion aparte: sobrevive a la reversion de la transaccion de carga."""
    with psycopg.connect(dsn(), autocommit=True) as c:
        r = c.execute(sql, params).fetchone() if "returning" in sql else c.execute(sql, params)
        return r[0] if isinstance(r, tuple) else None


def migrate(conn: psycopg.Connection) -> None:
    conn.execute("create table if not exists public.schema_migrations (version text primary key, aplicado_en timestamptz default now())")
    done = {r[0] for r in conn.execute("select version from public.schema_migrations")}
    for f in sorted(MIGRATIONS.glob("*.sql")):
        if f.name not in done:
            log.info("aplicando migracion %s", f.name)
            conn.execute(f.read_text(encoding="utf-8"))
            conn.execute("insert into public.schema_migrations(version) values (%s)", (f.name,))


# INFOBRAS nombra "P C DEL CALLAO" a la Provincia Constitucional que las demas fuentes llaman "CALLAO"
DEPARTAMENTO_CANONICO = {"P C DEL CALLAO": "CALLAO"}
TEXTOS_UI = {"explicacion", "cartera_explicacion", "simulacion"}


def textos_factores(df: pd.DataFrame, table: str) -> list[str]:
    """Frase en lenguaje claro de cada factor a partir de la variable y su valor real (las categorias se leen de la descripcion original)."""
    fn = factor_cuaderno if table == "explicacion" else factor_cartera
    return [fn(f, v, categoria(d) if v is None else None) for f, v, d in zip(df["feature"], df["valor"], df["descripcion"], strict=True)]


def copy_df(conn: psycopg.Connection, table: str, df: pd.DataFrame) -> None:
    if df.empty:
        return
    df = df.replace({np.nan: None})
    if table in TEXTOS_UI:  # textos generados para la interfaz: lenguaje claro y ortografia con tildes
        df = df.copy()
        if table in ("explicacion", "cartera_explicacion"):
            df["descripcion"] = textos_factores(df, table)
            df["grupo"] = df["grupo"].map(lambda g: GRUPOS_CLAROS.get(acentuar(g), GRUPOS_CLAROS.get(g, g)))
        for c in ("descripcion", "grupo"):
            if c in df.columns:
                df[c] = df[c].map(acentuar)
    cols = ", ".join(df.columns)
    with conn.cursor() as cur:
        with cur.copy(f"copy sato.{table} ({cols}) from stdin") as cp:
            for row in df.itertuples(index=False, name=None):
                cp.write_row(row)
    log.info("  %s: %s filas", table, len(df))


def _date(s):
    return pd.to_datetime(s, errors="coerce").dt.date


def copy_asientos(conn: psycopg.Connection, ids: set) -> int:
    """Asientos nacionales transferidos por lotes (DuckDB -> COPY) sin cargar todo en memoria. Devuelve las filas de origen."""
    import duckdb

    con = duckdb.connect()
    con.register("ids", pd.DataFrame({"cuaderno_id": sorted(ids)}))
    origen = con.sql(f"select count(*) from '{(CURATED / 'asiento.parquet').as_posix()}'").fetchone()[0]
    rel = con.sql(f"""
        select cuaderno_id, nro_asiento, fecha, fecha_hora, rol, tipo, tipo_std, titulo, descripcion, src_file archivo_fuente
        from (select *, row_number() over (partition by cuaderno_id, nro_asiento, fecha_hora, descripcion) rn
              from '{(CURATED / 'asiento.parquet').as_posix()}' where cuaderno_id in (select cuaderno_id from ids))
        where rn = 1 order by cuaderno_id, fecha_hora, nro_asiento""")
    cols = "cuaderno_id, nro_asiento, fecha, fecha_hora, rol, tipo, tipo_std, titulo, descripcion, archivo_fuente"
    n = 0
    reader = rel.fetch_record_batch(100_000)
    with conn.cursor() as cur:
        with cur.copy(f"copy sato.asiento ({cols}) from stdin") as cp:
            for batch in reader:
                for row in zip(*[batch.column(i).to_pylist() for i in range(batch.num_columns)], strict=True):
                    cp.write_row(row)
                n += batch.num_rows
    log.info("  asiento: %s filas", n)
    return origen


def load_cartera(conn: psycopg.Connection, cart: pd.DataFrame, cartera: Path, mef: pd.DataFrame, cua: pd.DataFrame, conc: dict) -> None:
    coords = mef.drop_duplicates("cui").set_index("cui")[["latitud", "longitud"]]
    ok = coords["latitud"].between(-18.6, 0.1) & coords["longitud"].between(-81.5, -68.5)
    coords = coords[ok]
    link = pd.read_parquet(CURATED / "link_cuaderno_infobras.parquet").drop_duplicates("codigo_infobras").set_index("codigo_infobras")["cuaderno_id"]
    link = link[link.isin(set(cua["cuaderno_id"]))]
    c = cart.drop_duplicates("codigo_infobras")
    conc["cartera_obra"] = {"origen": len(cart), "motivo": "códigos INFOBRAS repetidos"}
    copy_df(conn, "cartera_obra", pd.DataFrame(dict(
        codigo_infobras=c["codigo_infobras"], cui=c["codigo_unico_de_inversion"], nombre=c["nombre_de_obra"], entidad=c["entidad_publica"],
        codigo_entidad=c["codigo_entidad"], ruc_ejecucion=c["ruc_ejecucion"], contratista=c["nombre_o_razon_social_de_la_empresa_o_consorcio"],
        departamento=c["departamento"].replace(DEPARTAMENTO_CANONICO), provincia=c["provincia"], distrito=c["distrito"], estado_ejecucion=c["estado_de_ejecucion"],
        estado_operativo=c["estado_operativo"], fecha_inicio=_date(c["fecha_de_inicio_de_obra"]),
        plazo_dias=pd.to_numeric(c["plazo_de_ejecucion_en_dias"], errors="coerce").round().astype("Int64"), fin_programado=_date(c["fin_prog"]),
        fin_real=_date(c["fecha_de_finalizacion_real"]), sobreplazo=c["sobreplazo"], costo=c["costo_de_obra_en_soles_segun_et_en_soles"],
        modalidad=c["modalidad_de_ejecucion_de_la_obra"], tipo_obra=c["tipo_de_obra_clasificador_nivel_1"], retraso_significativo=c["y_30"].astype("Int64"),
        latitud=c["codigo_unico_de_inversion"].map(coords["latitud"]), longitud=c["codigo_unico_de_inversion"].map(coords["longitud"]),
        cuaderno_id=c["codigo_infobras"].map(link))))
    R = pd.read_parquet(cartera / "riesgo.parquet")
    conc["cartera_riesgo"] = {"origen": len(R), "motivo": "estimaciones de obras que no están en la cartera cargada"}
    R = R[R["codigo_infobras"].isin(set(c["codigo_infobras"]))]
    copy_df(conn, "cartera_riesgo", pd.DataFrame(dict(
        codigo_infobras=R["codigo_infobras"], tipo=R["tipo"], fecha_corte=_date(R["T"]), score=R["score"], nivel=R["nivel"],
        y_observado=R["y_observado"].astype("Int64"), modelo_origen=R["modelo_origen"])))
    rid = pd.DataFrame(conn.execute("select id, codigo_infobras, tipo, fecha_corte from sato.cartera_riesgo").fetchall(),
                       columns=["riesgo_id", "codigo_infobras", "tipo", "T"])
    rid["T"] = pd.to_datetime(rid["T"])
    E = pd.read_parquet(cartera / "explicaciones.parquet")
    conc["cartera_explicacion"] = {"origen": len(E), "motivo": "factores de estimaciones no cargadas"}
    E["T"] = pd.to_datetime(E["T"])
    E = E.merge(rid, on=["codigo_infobras", "tipo", "T"])
    copy_df(conn, "cartera_explicacion", E[["riesgo_id", "rango", "feature", "grupo", "valor", "shap", "descripcion"]])
    card = json.loads((cartera / "cartera_card.json").read_text(encoding="utf-8"))
    conn.execute("insert into sato.configuracion values ('modelo_cartera', %s)", (json.dumps(card, default=str),))


def load(release: Path = ARTIFACTS / "release", cartera: Path = ARTIFACTS / "cartera") -> dict:
    """Carga completa con validacion, conciliacion y compuerta de integridad. Devuelve el registro de la carga."""
    with psycopg.connect(dsn()) as c0:
        migrate(c0)
        c0.commit()
    cid = _registro("insert into sato.carga_datos (estado) values ('EN_CURSO') returning id", ())
    log.info("carga %s: lectura y validacion de entradas", cid)
    conc: dict[str, dict] = {}
    validacion: dict = {"max_caida": max_caida()}
    try:
        res = _cargar(release, cartera, conc, validacion)
    except CargaRechazada as e:
        _registro("update sato.carga_datos set fin = now(), estado = 'RECHAZADA', validacion = %s, conciliacion = %s, mensaje = %s where id = %s",
                  (json.dumps(validacion, default=str), json.dumps(conc, default=str), str(e)[:4000], cid))
        log.error("carga rechazada por la compuerta de integridad: %s", e)
        raise
    except Exception as e:
        _registro("update sato.carga_datos set fin = now(), estado = 'ERROR', validacion = %s, mensaje = %s where id = %s",
                  (json.dumps(validacion, default=str), f"{type(e).__name__}: {e}"[:4000], cid))
        raise
    _registro("update sato.carga_datos set fin = now(), estado = 'OK', conteos = %s, conciliacion = %s, validacion = %s where id = %s",
              (json.dumps(res), json.dumps(conc, default=str), json.dumps(validacion, default=str), cid))
    mantenimiento()
    return {"id": cid, "conteos": res, "conciliacion": conc, "validacion": validacion}


def max_caida() -> float:
    """Caida maxima de filas admitida en las tablas clave (parametro de operacion leido en cada carga)."""
    return float(os.environ.get("SATO_CARGA_CAIDA_MAX", "0.2"))


def _cargar(release: Path, cartera: Path, conc: dict, validacion: dict) -> dict[str, int]:
    from sato.serving import calidad

    cua = pd.read_parquet(CURATED / "cuaderno.parquet")
    n_cuadernos = len(cua)
    cua = cua[cua["tiene_metadatos"]].copy()
    ids = set(cua["cuaderno_id"])
    mef = pd.read_parquet(STAGING / "mef_inversiones.parquet")
    cart = pd.read_parquet(cartera / "obras.parquet") if (cartera / "obras.parquet").exists() else None
    cuis = set(cua["cui"].dropna()) | (set(cart["codigo_unico_de_inversion"].dropna()) if cart is not None else set())
    ib_link = pd.read_parquet(CURATED / "link_cuaderno_infobras.parquet")
    ib = pd.read_parquet(STAGING / "infobras_obras.parquet")
    seace = pd.read_parquet(STAGING / "seace_contratos.parquet")
    card = json.loads((release / "modelo_card.json").read_text(encoding="utf-8"))
    P_all = pd.read_parquet(release / "predicciones.parquet")
    validacion["entradas"] = validar_entradas({"cuaderno": cua, "mef_inversiones": mef, "infobras_obras": ib, "seace_contratos": seace,
                                               "predicciones": P_all, "cartera_obras": cart})
    if validacion["entradas"]:
        raise CargaRechazada("entradas invalidas: " + "; ".join(validacion["entradas"]))

    with psycopg.connect(dsn(), autocommit=False) as conn:
        conn.execute("set search_path to sato, public")
        previos = conteos(conn)
        log.info("borrando la version vigente (los lectores la siguen viendo hasta el COMMIT)")
        # DELETE (no TRUNCATE): TRUNCATE toma un bloqueo exclusivo que deja a la API sin poder leer durante toda la carga;
        # con DELETE los lectores siguen viendo los datos vigentes (MVCC) hasta el COMMIT, que cambia todo de una vez.
        for t in DATA_TABLES:  # orden de hijas a padres (claves foraneas)
            conn.execute(f"delete from sato.{t}")

        # linaje
        man = RAW / "manifest.jsonl"
        if man.exists():
            m = pd.read_json(man, lines=True).drop_duplicates("path", keep="last")
            copy_df(conn, "fuente_archivo", m.rename(columns={"source": "fuente", "path": "ruta", "last_modified": "last_modified",
                                                               "downloaded_at": "descargado_en"})[["fuente", "url", "ruta", "bytes", "sha256", "last_modified", "descargado_en"]])
        conn.execute("insert into sato.corte_datos (fecha_corte, descripcion) values (%s, %s)",
                     (card["fecha_corte_datos"], f"Release {card['version']}"))

        # actores
        ent = cua[["ruc_entidad", "entidad"]].dropna().drop_duplicates("ruc_entidad").rename(columns={"ruc_entidad": "ruc", "entidad": "nombre"})
        copy_df(conn, "entidad", ent)
        con = cua[["ruc_contratista", "contratista"]].dropna().drop_duplicates("ruc_contratista").rename(columns={"ruc_contratista": "ruc", "contratista": "nombre"})
        copy_df(conn, "contratista", con)

        # inversiones enlazadas a obras (cuaderno digital o cartera INFOBRAS)
        inv = mef[mef["cui"].isin(cuis)].copy()
        conc["inversion"] = {"origen": len(mef), "motivo": "inversiones sin obra con cuaderno digital ni obra de la cartera INFOBRAS"}
        inv["sector"] = np.select(
            [inv["funcion"].eq("SANEAMIENTO") | (inv["funcion"].eq("SALUD Y SANEAMIENTO") & inv["programa"].fillna("").str.contains("SANEAMIENTO")),
             inv["funcion"].eq("TRANSPORTE"), inv["funcion"].fillna("").str.startswith("EDUCACI"), inv["funcion"].isin(["SALUD", "SALUD Y SANEAMIENTO"]),
             inv["funcion"].isin(["AGROPECUARIA", "AGRARIA"])],
            ["SANEAMIENTO", "TRANSPORTE", "EDUCACION", "SALUD", "AGROPECUARIA"], "OTROS")
        copy_df(conn, "inversion", pd.DataFrame(dict(
            cui=inv["cui"], nombre=inv["nombre"], funcion=inv["funcion"], sector=inv["sector"], nivel_gobierno=inv["nivel"],
            tipo_inversion=inv["tipo_inversion"], monto_viable=inv["monto_viable"], costo_actualizado=inv["costo_actualizado"],
            estado=inv["estado"], fuente=inv["fuente"], departamento=inv["departamento"], provincia=inv["provincia"], distrito=inv["distrito"],
            ubigeo=inv["ubigeo"], latitud=inv["latitud"], longitud=inv["longitud"], fecha_corte=_date(inv["fecha_corte"]))))
        sector_by_cui = inv.set_index("cui")["sector"]

        # obras
        cua = cua.merge(ib_link.rename(columns={"metodo": "infobras_metodo"}), on="cuaderno_id", how="left")
        cua = cua.merge(ib[["codigo_infobras", "plazo_de_ejecucion_en_dias", "monto_del_contrato_en_soles"]], on="codigo_infobras", how="left")
        s1 = seace.drop_duplicates("n_cod_contrato")[["n_cod_contrato", "urlcontrato"]].rename(columns={"n_cod_contrato": "contrato_id"})
        cua = cua.merge(s1, on="contrato_id", how="left")
        fin = pd.concat([pd.to_datetime(cua[c]) for c in ("f_culminacion", "f_recepcion", "f_cierre")], axis=1).min(axis=1)
        D = pd.Timestamp(card["fecha_corte_datos"])
        estado = np.where(cua["f_resolucion_contrato"].notna(), "RESUELTA", np.where(fin.notna(), "CULMINADA",
                          np.where(pd.to_datetime(cua["ultimo_asiento"]) < D - pd.Timedelta(days=90), "INACTIVA", "EN_EJECUCION")))
        onset = pd.concat([pd.to_datetime(cua[c]) for c in ("f_valorizacion_menor_80", "f_calendario_acelerado")], axis=1).min(axis=1)
        obra = pd.DataFrame(dict(
            cuaderno_id=cua["cuaderno_id"], contrato_id=cua["contrato_id"], expediente_id=cua["expediente_id"], denominacion=cua["denominacion"],
            entidad_ruc=cua["ruc_entidad"], contratista_ruc=cua["ruc_contratista"], es_consorcio=cua["es_consorcio"], ubigeo=cua["ubigeo"],
            departamento=cua["departamento"], provincia=cua["provincia"], distrito=cua["distrito"], latitud=cua["latitud"], longitud=cua["longitud"],
            cui=cua["cui"].where(cua["cui"].isin(set(inv["cui"]))), cui_metodo_enlace=cua["link_method"], cui_score_enlace=cua["link_score"],
            codigo_infobras=cua["codigo_infobras"], infobras_metodo=cua["infobras_metodo"],
            sector=cua["cui"].map(sector_by_cui).fillna("SIN_CUI"),
            plazo_original_dias=pd.to_numeric(cua["plazo_de_ejecucion_en_dias"], errors="coerce").where(lambda s: s > 0).astype("Int64"),
            monto_contrato=cua["monto_del_contrato_en_soles"], url_contrato_seace=cua["urlcontrato"],
            primer_asiento=_date(cua["primer_asiento"]), ultimo_asiento=_date(cua["ultimo_asiento"]), n_asientos=cua["n_asientos"].astype("Int64"),
            historia_completa=cua["historia_completa"], fecha_atraso=onset.dt.date, fecha_suspension=_date(cua["f_suspension_plazo"]),
            fecha_culminacion=_date(cua["f_culminacion"]), fecha_recepcion=_date(cua["f_recepcion"]),
            fecha_resolucion=_date(cua["f_resolucion_contrato"]), estado_observado=estado))
        copy_df(conn, "obra", obra)
        conc["obra"] = {"origen": n_cuadernos, "motivo": "cuadernos sin metadatos del contrato en OECE"}

        # asientos nacionales (deduplicados, por lotes)
        conc["asiento"] = {"origen": copy_asientos(conn, ids),
                           "motivo": "asientos de cuadernos sin metadatos del contrato o repetidos (misma obra, número, fecha-hora y texto)"}

        # SIAF mensual de las CUI enlazadas
        siaf = pd.concat([pd.read_parquet(f, columns=["cui", "anio", "mes", "monto_devengado"]) for f in sorted((STAGING / "siaf").glob("*.parquet"))])
        conc["siaf_mensual"] = {"origen": len(siaf), "motivo": "registros de CUI no enlazadas, mes fuera de 1-12 o anteriores a 2017; "
                                                               "los demás se agregan por CUI y mes"}
        siaf = siaf[siaf["cui"].isin(set(inv["cui"])) & siaf["mes"].between(1, 12) & (siaf["anio"] >= 2017)].groupby(["cui", "anio", "mes"], as_index=False)["monto_devengado"].sum()
        copy_df(conn, "siaf_mensual", siaf.rename(columns={"monto_devengado": "devengado"}))

        # INFOBRAS (foto) nacional
        iba = ib.drop_duplicates("codigo_infobras")
        conc["infobras_obra"] = {"origen": len(ib), "motivo": "códigos INFOBRAS repetidos"}
        copy_df(conn, "infobras_obra", pd.DataFrame(dict(
            codigo_infobras=iba["codigo_infobras"], cui=iba["codigo_unico_de_inversion"], nombre=iba["nombre_de_obra"], entidad=iba["entidad_publica"],
            estado_ejecucion=iba["estado_de_ejecucion"], modalidad=iba["modalidad_de_ejecucion_de_la_obra"],
            fecha_inicio_obra=_date(iba["fecha_de_inicio_de_obra"]), fecha_fin_programada=_date(iba["fecha_finalizacion_programada_de_obra"]),
            fecha_fin_reprogramada=_date(iba["fecha_finalizacion_reprogramada_de_obra"]), fecha_fin_real=_date(iba["fecha_de_finalizacion_real"]),
            plazo_dias=pd.to_numeric(iba["plazo_de_ejecucion_en_dias"], errors="coerce").astype("Int64"),
            avance_fisico_programado=iba["avance_fisico_programado_acumulado"], avance_fisico_real=iba["avance_fisico_real_acumulado"],
            existe_paralizacion=iba["existe_paralizacion"], causal_paralizacion=iba["causal_de_paralizacion"],
            fecha_paralizacion=_date(iba["fecha_de_paralizacion"]),
            n_modificaciones_plazo=pd.to_numeric(iba["n_de_modificaciones"], errors="coerce").astype("Int64"),
            dias_modificacion_plazo=pd.to_numeric(iba["n_dias_de_modificaciones_de_plazo"], errors="coerce").astype("Int64"),
            n_adicionales=pd.to_numeric(iba["n_de_adicionales_de_obra"], errors="coerce").astype("Int64"),
            fecha_consulta=_date(iba["fecha_consulta"]))))

        par = pd.read_parquet(STAGING / "contraloria_paralizadas.parquet")
        conc["contraloria_paralizada"] = {"origen": len(par), "motivo": "-"}
        copy_df(conn, "contraloria_paralizada", pd.DataFrame(dict(
            fecha_corte=_date(par["fecha_corte"]), codigo_infobras=par["codigo_infobras"], cui=par["cui"], descripcion_obra=par["descripcion_obra"],
            entidad=par["entidad"], provincia=par["provincia"], distrito=par["distrito"], avance_fisico=par["avance_fisico"],
            causal=par["causal_paralizacion"], sector=par["sector"])))

        ms = pd.read_parquet(STAGING / "mef_estado_situacional.parquet")
        cuis_seg = set(cua["cui"].dropna())
        if cart is not None:
            cuis_seg |= set(cart.loc[cart["estado_operativo"].isin(["ACTIVA", "CONSUMADO"]), "codigo_unico_de_inversion"].dropna())
        conc["mef_seguimiento"] = {"origen": len(ms), "motivo": "registros sin fecha o de inversiones no evaluadas"}
        ms = ms[ms["cui"].isin(cuis_seg) & ms["fecha_registro"].notna()]
        copy_df(conn, "mef_seguimiento", ms[["cui", "fecha_registro", "tipo_registro", "descripcion"]])

        # modelo, predicciones, explicaciones, evidencia
        mid = conn.execute(
            """insert into sato.modelo (nombre, version, objetivo, horizonte_dias, conjunto_features, algoritmo, entrenado_hasta,
                 umbral_alerta, metricas, features, artefacto, sha256, activo) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,true) returning id""",
            (card["nombre"], card["version"], card["objetivo"], card["horizonte_dias"], card["conjunto_features"], card["algoritmo"],
             card["entrenado_hasta"], card["umbral_alerta"], json.dumps({**card["metricas_test"], "umbral_alto": card["umbral_alto"], "umbral_vigilancia": card.get("umbral_vigilancia"),
                                                                          "operacion_backtest_arequipa": card.get("operacion_backtest_arequipa"),
                                                                          "operacion_backtest_nacional": card.get("operacion_backtest_nacional"),
                                                                          "periodos": card["periodos_evaluacion"]}, default=str),
             json.dumps(card["features"]), card["artefacto"], card["sha256"])).fetchone()[0]
        P = P_all[P_all["cuaderno_id"].isin(ids)]
        conc["prediccion"] = {"origen": len(P_all), "motivo": "predicciones de cuadernos sin metadatos del contrato"}
        copy_df(conn, "prediccion", pd.DataFrame(dict(
            modelo_id=mid, cuaderno_id=P["cuaderno_id"], fecha_corte=_date(P["T"]), tipo=P["tipo"], score=P["score"], percentil=P["percentil"],
            nivel=P["nivel"], alerta=P["alerta"], y_observado=P["y_observado"].astype("Int64"))))
        pid = pd.DataFrame(conn.execute("select id, cuaderno_id::text, fecha_corte from sato.prediccion").fetchall(), columns=["prediccion_id", "cuaderno_id", "T"])
        pid["T"] = pd.to_datetime(pid["T"])
        E = pd.read_parquet(release / "explicaciones.parquet")
        conc["explicacion"] = {"origen": len(E), "motivo": "factores de predicciones no cargadas"}
        E = E.merge(pid, on=["cuaderno_id", "T"])
        copy_df(conn, "explicacion", E[["prediccion_id", "rango", "feature", "grupo", "valor", "shap", "descripcion"]])
        ev = pd.read_parquet(release / "evidencia.parquet")
        conc["evidencia"] = {"origen": len(ev), "motivo": "evidencia de predicciones no cargadas"}
        ev = ev.merge(pid, on=["cuaderno_id", "T"])
        aid = pd.DataFrame(conn.execute("select min(id), cuaderno_id::text, nro_asiento from sato.asiento group by 2, 3").fetchall(),
                           columns=["asiento_id", "cuaderno_id", "nro_asiento"])
        if "nro_asiento" in ev.columns:
            ev = ev.merge(aid, on=["cuaderno_id", "nro_asiento"], how="left")
        else:
            ev["asiento_id"] = None
        ev["fecha"] = _date(ev["fecha"])
        ev["asiento_id"] = ev["asiento_id"].astype("Int64")
        copy_df(conn, "evidencia", ev[["prediccion_id", "feature", "fuente", "asiento_id", "fecha", "referencia", "extracto"]])
        simp = release / "simulaciones.parquet"
        if simp.exists():
            sm = pd.read_parquet(simp)
            conc["simulacion"] = {"origen": len(sm), "motivo": "escenarios de predicciones no cargadas"}
            sm = sm.merge(pid, on=["cuaderno_id", "T"])
            copy_df(conn, "simulacion", sm[["prediccion_id", "escenario", "descripcion", "score_base", "score_escenario", "alerta_escenario"]])
        conn.execute("insert into sato.configuracion values ('modelo_cuaderno', %s)", (json.dumps(card, default=str),))

        # cartera nacional INFOBRAS (modelos de inicio y seguimiento)
        if cart is not None:
            load_cartera(conn, cart, cartera, mef, cua, conc)

        # resultados de investigacion
        g = ARTIFACTS / "experiments" / "grid_resultados.csv"
        if g.exists():
            gr = pd.read_csv(g)
            gr = gr[gr.get("error").isna()] if "error" in gr.columns else gr
            keys = ["target", "H", "feature_set", "train_scope", "modelo", "test_scope"]
            met = gr.drop(columns=[c for c in gr.columns if c in keys or c == "error"])
            copy_df(conn, "experimento_resultado", pd.DataFrame(dict(
                objetivo=gr["target"], horizonte=gr["H"], conjunto_features=gr["feature_set"], alcance_entrenamiento=gr["train_scope"],
                modelo=gr["modelo"], alcance_test=gr["test_scope"], metricas=[json.dumps({k: (None if pd.isna(v) else v) for k, v in r.items()}) for r in met.to_dict("records")])))
        c = ARTIFACTS / "experiments" / "comparacion_A_vs_B.csv"
        if c.exists():
            cp = pd.read_csv(c).rename(columns={"target": "objetivo", "H": "horizonte", "test_scope": "alcance_test", "A": "a", "B": "b"})
            copy_df(conn, "comparacion_ab", cp[["objetivo", "horizonte", "variante", "alcance_test", "metrica", "a", "b", "diferencia", "ic_inf", "ic_sup", "p_valor", "filas", "obras"]])

        # vistas derivadas, reporte de monitoreo del modelo y compuerta de integridad antes de confirmar
        log.info("vistas derivadas, auditoria de calidad y compuerta de integridad")
        conn.execute("refresh materialized view concurrently sato.cartera_riesgo_vigente")  # sin bloquear lecturas
        conn.execute("refresh materialized view concurrently sato.obra_prediccion_vigente")
        mon = ARTIFACTS / "monitoring" / "reporte.json"
        if mon.exists():
            rep = json.loads(mon.read_text(encoding="utf-8"))
            # nombre legible de cada variable con deriva para la interfaz (sin codigos internos)
            rep["psi_detalle"] = [{"variable": f, "etiqueta": etiqueta(f, "cuaderno"), "psi": v} for f, v in (rep.get("psi_ultimo_corte") or {}).items()]
            conn.execute("insert into sato.configuracion values ('monitoreo_modelo', %s)", (json.dumps(rep, default=str),))
        nuevos = conteos(conn)
        for t, x in conc.items():
            x["cargadas"] = nuevos.get(t, 0)
            x["descartadas"] = x["origen"] - x["cargadas"]
        out = calidad.evaluar(conn)
        validacion["criticos"] = [f"{x['descripcion']}: {x['valor']:,}" for x in calidad.criticos(out)]
        validacion["caidas"] = compuerta(previos, nuevos, max_caida())
        validacion["forzada"] = bool(validacion["caidas"]) and os.environ.get("SATO_CARGA_FORZAR") == "1"
        validacion["previos"] = {t: previos[t] for t in TABLAS_CLAVE}
        if validacion["criticos"]:
            raise CargaRechazada("chequeos criticos con hallazgos: " + "; ".join(validacion["criticos"]))
        if validacion["caidas"] and not validacion["forzada"]:
            raise CargaRechazada("caida de filas en tablas clave: " + "; ".join(validacion["caidas"]))
        calidad.guardar(conn, out)
        conn.commit()
    log.info("base de datos cargada: %s", {t: nuevos[t] for t in TABLAS_CLAVE})
    return nuevos


def mantenimiento() -> None:
    """Recupera el espacio de las filas reemplazadas y actualiza las estadisticas del planificador.

    Se ejecuta despues del COMMIT: si falla, la nueva version ya esta publicada; solo se registra el aviso
    (autovacuum lo completara despues)."""
    try:
        with psycopg.connect(dsn(), autocommit=True) as c:
            for t in [*DATA_TABLES, "cartera_riesgo_vigente", "obra_prediccion_vigente"]:
                c.execute(f"vacuum (analyze) sato.{t}")
    except psycopg.Error as e:
        log.warning("mantenimiento posterior a la carga incompleto (%s: %s); lo completara autovacuum", type(e).__name__, e)


def ensure_admin() -> None:
    """Crea el usuario administrador desde variables de entorno (nunca con credenciales por defecto)."""
    import bcrypt

    email, pwd = os.environ.get("SATO_ADMIN_EMAIL"), os.environ.get("SATO_ADMIN_PASSWORD")
    if not email or not pwd:
        log.info("SATO_ADMIN_EMAIL/SATO_ADMIN_PASSWORD no definidos: no se crea administrador")
        return
    h = bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()
    with psycopg.connect(dsn()) as conn:
        conn.execute("""insert into sato.usuario (email, nombre, rol, password_hash) values (%s, %s, 'admin', %s)
                        on conflict (email) do update set password_hash = excluded.password_hash""", (email, "Administrador", h))
    log.info("administrador asegurado: %s", email)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    load()
    ensure_admin()
