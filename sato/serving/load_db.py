"""Carga idempotente de la base de datos de la plataforma (PostgreSQL).

    DATABASE_URL=postgresql://... python -m sato.serving.load_db

1. Aplica migraciones SQL pendientes (db/migrations/*.sql, tabla schema_migrations).
2. En UNA transaccion: vacia las tablas de datos y las recarga desde data/curated,
   data/staging y artifacts/release (solo Arequipa para datos de obra; los datos
   nacionales solo se usan para entrenar). Usuarios, revisiones y auditoria no se tocan.
3. Registra el corte de datos y el linaje (manifest.jsonl).
Si algo falla, la transaccion se revierte y la base queda como estaba.
"""

from __future__ import annotations

import io
import json
import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg

from sato.config import ARTIFACTS, CURATED, RAW, ROOT, STAGING

log = logging.getLogger(__name__)
MIGRATIONS = ROOT / "db" / "migrations"
DATA_TABLES = ["evidencia", "explicacion", "prediccion", "modelo", "asiento", "obra", "inversion", "entidad", "contratista",
               "siaf_mensual", "infobras_obra", "contraloria_paralizada", "mef_seguimiento", "experimento_resultado",
               "comparacion_ab", "fuente_archivo", "corte_datos"]


def dsn() -> str:
    url = os.environ.get("DATABASE_URL", "postgresql://sato:sato@127.0.0.1:5432/sato")
    return url.replace("postgresql+psycopg://", "postgresql://")


def migrate(conn: psycopg.Connection) -> None:
    conn.execute("create table if not exists public.schema_migrations (version text primary key, aplicado_en timestamptz default now())")
    done = {r[0] for r in conn.execute("select version from public.schema_migrations")}
    for f in sorted(MIGRATIONS.glob("*.sql")):
        if f.name not in done:
            log.info("aplicando migracion %s", f.name)
            conn.execute(f.read_text(encoding="utf-8"))
            conn.execute("insert into public.schema_migrations(version) values (%s)", (f.name,))


def copy_df(conn: psycopg.Connection, table: str, df: pd.DataFrame) -> None:
    if df.empty:
        return
    df = df.replace({np.nan: None})
    cols = ", ".join(df.columns)
    with conn.cursor() as cur:
        with cur.copy(f"copy sato.{table} ({cols}) from stdin") as cp:
            for row in df.itertuples(index=False, name=None):
                cp.write_row(row)
    log.info("  %s: %s filas", table, len(df))


def _date(s):
    return pd.to_datetime(s, errors="coerce").dt.date


def load(release: Path = ARTIFACTS / "release") -> None:
    cua = pd.read_parquet(CURATED / "cuaderno.parquet")
    cua = cua[cua["tiene_metadatos"] & (cua["dep_code"] == "04")].copy()
    ids = set(cua["cuaderno_id"])
    mef = pd.read_parquet(STAGING / "mef_inversiones.parquet")
    cuis = set(cua["cui"].dropna())
    ib_link = pd.read_parquet(CURATED / "link_cuaderno_infobras.parquet")
    ib = pd.read_parquet(STAGING / "infobras_obras.parquet")
    seace = pd.read_parquet(STAGING / "seace_contratos.parquet")
    card = json.loads((release / "modelo_card.json").read_text(encoding="utf-8"))

    with psycopg.connect(dsn(), autocommit=False) as conn:
        migrate(conn)
        conn.execute("set search_path to sato, public")
        conn.execute("truncate " + ", ".join(f"sato.{t}" for t in DATA_TABLES) + " restart identity cascade")

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

        # inversiones: las enlazadas a obras de Arequipa + todas las de Arequipa
        inv = mef[mef["cui"].isin(cuis) | (mef["departamento"] == "AREQUIPA")].copy()
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

        # asientos de Arequipa (deduplicados)
        asi = pd.read_parquet(CURATED / "asiento.parquet")
        asi = asi[asi["cuaderno_id"].isin(ids)].drop_duplicates(["cuaderno_id", "nro_asiento", "fecha_hora", "descripcion"])
        asi = asi.sort_values(["cuaderno_id", "fecha_hora", "nro_asiento"])
        copy_df(conn, "asiento", pd.DataFrame(dict(
            cuaderno_id=asi["cuaderno_id"], nro_asiento=asi["nro_asiento"], fecha=_date(asi["fecha"]), fecha_hora=asi["fecha_hora"],
            rol=asi["rol"], tipo=asi["tipo"], tipo_std=asi["tipo_std"], titulo=asi["titulo"], descripcion=asi["descripcion"],
            archivo_fuente=asi["src_file"])))

        # SIAF mensual de las CUI enlazadas y de Arequipa
        siaf = pd.concat([pd.read_parquet(f, columns=["cui", "anio", "mes", "monto_devengado"]) for f in sorted((STAGING / "siaf").glob("*.parquet"))])
        siaf = siaf[siaf["cui"].isin(set(inv["cui"])) & siaf["mes"].between(1, 12)].groupby(["cui", "anio", "mes"], as_index=False)["monto_devengado"].sum()
        copy_df(conn, "siaf_mensual", siaf.rename(columns={"monto_devengado": "devengado"}))

        # INFOBRAS (foto) de Arequipa
        iba = ib[(ib["departamento"] == "AREQUIPA") | ib["codigo_infobras"].isin(set(cua["codigo_infobras"].dropna()))].drop_duplicates("codigo_infobras")
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
        par = par[par["departamento"] == "AREQUIPA"]
        copy_df(conn, "contraloria_paralizada", pd.DataFrame(dict(
            fecha_corte=_date(par["fecha_corte"]), codigo_infobras=par["codigo_infobras"], cui=par["cui"], descripcion_obra=par["descripcion_obra"],
            entidad=par["entidad"], provincia=par["provincia"], distrito=par["distrito"], avance_fisico=par["avance_fisico"],
            causal=par["causal_paralizacion"], sector=par["sector"])))

        ms = pd.read_parquet(STAGING / "mef_estado_situacional.parquet")
        ms = ms[ms["cui"].isin(set(inv["cui"])) & ms["fecha_registro"].notna()]
        copy_df(conn, "mef_seguimiento", ms[["cui", "fecha_registro", "tipo_registro", "descripcion"]])

        # modelo, predicciones, explicaciones, evidencia
        mid = conn.execute(
            """insert into sato.modelo (nombre, version, objetivo, horizonte_dias, conjunto_features, algoritmo, entrenado_hasta,
                 umbral_alerta, metricas, features, artefacto, sha256, activo) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,true) returning id""",
            (card["nombre"], card["version"], card["objetivo"], card["horizonte_dias"], card["conjunto_features"], card["algoritmo"],
             card["entrenado_hasta"], card["umbral_alerta"], json.dumps({**card["metricas_test"], "umbral_alto": card["umbral_alto"], "umbral_vigilancia": card.get("umbral_vigilancia"),
                                                                          "operacion_backtest_arequipa": card.get("operacion_backtest_arequipa"),
                                                                          "periodos": card["periodos_evaluacion"]}, default=str),
             json.dumps(card["features"]), card["artefacto"], card["sha256"])).fetchone()[0]
        P = pd.read_parquet(release / "predicciones.parquet")
        P = P[P["cuaderno_id"].isin(ids)]
        copy_df(conn, "prediccion", pd.DataFrame(dict(
            modelo_id=mid, cuaderno_id=P["cuaderno_id"], fecha_corte=_date(P["T"]), tipo=P["tipo"], score=P["score"], percentil=P["percentil"],
            nivel=P["nivel"], alerta=P["alerta"], y_observado=P["y_observado"].astype("Int64"))))
        pid = pd.DataFrame(conn.execute("select id, cuaderno_id::text, fecha_corte from sato.prediccion").fetchall(), columns=["prediccion_id", "cuaderno_id", "T"])
        pid["T"] = pd.to_datetime(pid["T"])
        E = pd.read_parquet(release / "explicaciones.parquet").merge(pid, on=["cuaderno_id", "T"])
        copy_df(conn, "explicacion", E[["prediccion_id", "rango", "feature", "grupo", "valor", "shap", "descripcion"]])
        ev = pd.read_parquet(release / "evidencia.parquet").merge(pid, on=["cuaderno_id", "T"])
        aid = pd.DataFrame(conn.execute("select min(id), cuaderno_id::text, nro_asiento from sato.asiento group by 2, 3").fetchall(),
                           columns=["asiento_id", "cuaderno_id", "nro_asiento"])
        if "nro_asiento" in ev.columns:
            ev = ev.merge(aid, on=["cuaderno_id", "nro_asiento"], how="left")
        else:
            ev["asiento_id"] = None
        ev["fecha"] = _date(ev["fecha"])
        ev["asiento_id"] = ev["asiento_id"].astype("Int64")
        copy_df(conn, "evidencia", ev[["prediccion_id", "feature", "fuente", "asiento_id", "fecha", "referencia", "extracto"]])

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
        conn.commit()
    log.info("base de datos cargada")


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
