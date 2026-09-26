"""Resolucion de entidades: Cuaderno de Obra Digital (OECE) -> CUI (Invierte.pe) -> INFOBRAS.

Los cuadernos OECE no traen CUI. Se aplica una cascada, del metodo mas
confiable al menos confiable, y se registra el metodo y la evidencia de cada
enlace (lineage):

1. `regex_cui`   : la denominacion de la obra cita "CUI N° 2xxxxxx" /
                   "Codigo Unico de Inversion ..." y el codigo existe en el
                   Banco de Inversiones.
2. `regex_snip`  : cita un codigo SNIP que mapea a un unico CUI.
3. `bare_7digit` : contiene un numero de 7 digitos que empieza en 2 y existe
                   como CUI (menos especifico; se reporta aparte).
4. `fuzzy_tfidf` : similitud coseno TF-IDF de n-gramas de caracteres (3-5)
                   entre la denominacion normalizada y NOMBRE_INVERSION,
                   bloqueando por departamento (UBIGEO). Se acepta solo si
                   score >= 0.60 y margen sobre el 2do candidato >= 0.05.
                   Umbrales calibrados contra los enlaces `regex_cui` usados
                   como verdad de referencia: precision 0.991, cobertura 0.906
                   (ver docs/research/EVIDENCE_LOG.md, E4).

No se aplica fuzzy matching cuando existe un identificador confiable.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from sato.config import CURATED, STAGING

log = logging.getLogger(__name__)

FUZZY_MIN_SCORE = 0.60
FUZZY_MIN_MARGIN = 0.05

RX_CUI = re.compile(
    r"(?:C\.?\s*U\.?\s*I\.?|CODIGO\s+UNICO(?:\s+DE\s+INVERSION(?:ES)?)?|COD\.?\s*UNICO)"
    r"\s*(?:N\s*[O°º]?\.?|NRO\.?|NUMERO)?\s*[:\-\.]?\s*(\d{6,7})"
)
RX_SNIP = re.compile(r"SNIP\s*(?:N\s*[O°º]?\.?|NRO\.?)?\s*[:\-\.]?\s*(\d{4,7})")
RX_ANY7 = re.compile(r"\b(2\d{6})\b")


def ascii_upper(s) -> str:
    if not isinstance(s, str):
        return ""
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper()


def norm_name(s) -> str:
    s = ascii_upper(s)
    s = re.sub(r"(C\.?U\.?I\.?|CODIGO UNICO[A-Z ]*|SNIP)\s*(N[O°]?\.?|NRO\.?)?\s*[:\-]?\s*\d+", "", s)
    s = re.sub(r"^.*?(EJECUCION DE (LA )?(OBRA|SALDO DE OBRA)[: ]*|CONTRATACION DE[A-Z ]*?OBRA[: ]*)", "", s)
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def regex_link(cuadernos: pd.DataFrame, mef: pd.DataFrame) -> pd.DataFrame:
    cuis = set(mef["cui"])
    snip_counts = mef[mef["snip"].notna() & ~mef["snip"].isin(["", "0"])].groupby("snip")["cui"].nunique()
    snip2cui = mef[mef["snip"].isin(snip_counts[snip_counts == 1].index)].drop_duplicates("snip").set_index("snip")["cui"].to_dict()
    rows = []
    for r in cuadernos.itertuples():
        t = ascii_upper(r.denominacion)
        cand, how = [x for x in RX_CUI.findall(t) if x in cuis], None
        if cand:
            how = "regex_cui"
        else:
            s = [snip2cui[x] for x in RX_SNIP.findall(t) if x in snip2cui]
            if s:
                cand, how = s, "regex_snip"
            else:
                a = [x for x in RX_ANY7.findall(t) if x in cuis]
                if a:
                    cand, how = a, "bare_7digit"
        rows.append((r.cuaderno_id, how, cand[0] if cand else None, len(set(cand))))
    return pd.DataFrame(rows, columns=["cuaderno_id", "method", "cui", "n_candidates"])


def fuzzy_link(cuadernos: pd.DataFrame, mef: pd.DataFrame) -> pd.DataFrame:
    mef = mef.assign(dep=mef["ubigeo"].fillna("").str[:2], n=mef["nombre"].map(norm_name))
    cua = cuadernos.assign(dep=cuadernos["ubigeo"].fillna("").str[:2], n=cuadernos["denominacion"].map(norm_name))
    out = []
    for dep, g in cua.groupby("dep"):
        m = mef[mef["dep"] == dep]
        if m.empty or not dep:
            out += [(c, None, 0.0, 0.0) for c in g["cuaderno_id"]]
            continue
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True).fit(pd.concat([m["n"], g["n"]]))
        A, B = vec.transform(g["n"]), vec.transform(m["n"])
        for i in range(0, A.shape[0], 500):
            sim = (A[i : i + 500] @ B.T).toarray()
            top = np.argsort(-sim, axis=1)[:, :2]
            for j, row in enumerate(top):
                s1 = float(sim[j, row[0]])
                s2 = float(sim[j, row[1]]) if len(row) > 1 else 0.0
                out.append((g["cuaderno_id"].iloc[i + j], m["cui"].iloc[row[0]], s1, s1 - s2))
    return pd.DataFrame(out, columns=["cuaderno_id", "cui_fuzzy", "fuzzy_score", "fuzzy_margin"])


def build(out: Path = CURATED) -> Path:
    mef = pd.read_parquet(STAGING / "mef_inversiones.parquet", columns=["cui", "snip", "nombre", "ubigeo"])
    cua = (
        pd.read_parquet(STAGING / "oece_cuadernos.parquet")
        .rename(columns={"NRO_CORRELATIVO_DE_CUADERNO_DE_OBRA": "cuaderno_id", "DENOMINACION_DE_LA_OBRA": "denominacion", "UBIGEO": "ubigeo"})
        .drop_duplicates("cuaderno_id")[["cuaderno_id", "denominacion", "ubigeo"]]
    )
    rx = regex_link(cua, mef)
    fz = fuzzy_link(cua, mef)
    link = rx.merge(fz, on="cuaderno_id", how="left")
    ok_fuzzy = (link["fuzzy_score"] >= FUZZY_MIN_SCORE) & (link["fuzzy_margin"] >= FUZZY_MIN_MARGIN)
    use_fuzzy = link["method"].isna() & ok_fuzzy
    link.loc[use_fuzzy, "cui"] = link.loc[use_fuzzy, "cui_fuzzy"]
    link.loc[use_fuzzy, "method"] = "fuzzy_tfidf"
    link["regex_fuzzy_agree"] = np.where(link["method"] == "regex_cui", link["cui"] == link["cui_fuzzy"], None)
    dst = out / "link_cuaderno_cui.parquet"
    link.to_parquet(dst, index=False)
    log.info("metodos: %s", link["method"].value_counts(dropna=False).to_dict())
    return dst


def build_infobras_link(out: Path = CURATED) -> Path:
    """Cuaderno -> obra INFOBRAS (deterministico, sin fuzzy):

    1. `cui_ruc`   : misma CUI y el RUC ejecutor INFOBRAS coincide con el RUC del
                     contratista o de un miembro del consorcio, y el match es unico.
    2. `cui_unico` : la CUI tiene una sola obra en INFOBRAS.
    En otro caso no se enlaza (ambiguo).
    """
    import duckdb

    con = duckdb.connect()
    con.sql(f"create table cua as select cuaderno_id, cui, ruc_contratista from '{(out / 'cuaderno.parquet').as_posix()}' where cui is not null")
    con.sql(f"create table mem as select distinct NRO_CORRELATIVO_DE_CUADERNO_DE_OBRA cuaderno_id, RUC_MIEMBRO_DEL_CONSORCIO ruc from '{(STAGING / 'oece_cuadernos.parquet').as_posix()}'")
    con.sql(f"create table ib as select codigo_infobras, codigo_unico_de_inversion cui, ruc_ejecucion from '{(STAGING / 'infobras_obras.parquet').as_posix()}' where codigo_unico_de_inversion is not null")
    dst = out / "link_cuaderno_infobras.parquet"
    con.sql(
        f"""
        copy (
          with cand as (
            select c.cuaderno_id, i.codigo_infobras,
                   (i.ruc_ejecucion = c.ruc_contratista or i.ruc_ejecucion in (select ruc from mem m where m.cuaderno_id = c.cuaderno_id)) ruc_ok,
                   count(*) over (partition by c.cuaderno_id) n_cui
            from cua c join ib i on i.cui = c.cui
          ),
          r as (select cuaderno_id, any_value(codigo_infobras) codigo_infobras, 'cui_ruc' AS metodo
                from cand where ruc_ok group by 1 having count(*) = 1),
          u as (select cuaderno_id, any_value(codigo_infobras) codigo_infobras, 'cui_unico' AS metodo
                from cand where n_cui = 1 and cuaderno_id not in (select cuaderno_id from r) group by 1)
          select * from r union all select * from u
        ) to '{dst.as_posix()}' (format parquet)
        """
    )
    log.info("cuaderno->infobras: %s", con.sql(f"select metodo, count(*) from '{dst.as_posix()}' group by 1").fetchall())
    return dst


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    build()
    build_infobras_link()
