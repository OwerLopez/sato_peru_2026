"""Features documentales (Modelo B) a partir del texto de los asientos.

Regla temporal: en el corte T solo se usan asientos con fecha <= T. Todo
componente con parametros ajustados a datos (vocabulario, IDF, SVD, PCA) se
ajusta SOLO con asientos/filas del periodo de entrenamiento (fecha <= FIT_END),
nunca con el periodo de test.

Representaciones (ventana de 60 dias: (T-60, T]):
  * lexicon  : proporcion de asientos de la ventana que mencionan cada categoria
               de causa de atraso (literatura: Assaf & Al-Hejji 2006; Sambasivan &
               Soon 2007) adaptada a la terminologia peruana de obra publica.
               La categoria `proxy_80` agrupa menciones informales de la propia
               regla del 80%/calendario acelerado y se usa en la ablacion
               "sin proxy" para medir cuanto de la ganancia es anticipacion
               genuina y cuanto es la misma anotacion hecha en otro tipo de asiento.
  * lsa      : TF-IDF (1-2 gramas) promedio de la ventana -> SVD truncado (64).
  * emb      : embeddings Sentence-BERT multilingues por asiento, promedio de la
               ventana -> PCA (32).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import scipy.sparse as sp

from sato.config import CURATED, FEATURES

log = logging.getLogger(__name__)

FIT_END = pd.Timestamp("2025-10-31")  # fin del periodo de entrenamiento (antes de TEST_START - H)
WINDOW_DAYS = 60

LEXICON = {
    "atraso": r"atras|retras|demora|no cumple.{0,25}(calendario|cronograma|programa)|bajo rendimiento|avance lento|avance minimo",
    "proxy_80": r"80 ?%|ochenta por ciento|calendario acelerado|cronograma acelerado|programa[a-z ]{0,25}acelerad|articulo 20[37]|art\. ?20[37]",
    "paralizacion": r"paraliz|obra detenida|no se (registra|ejecuta|realiza)[a-z ]{0,20}trabajo|sin personal en obra|abandono",
    "clima": r"lluvia|precipitac|huayco|inundac|friaje|helada|neblina|nevad|temporal",
    "financiero": r"falta de pago|pago pendiente|no se ha pagado|adelanto|deuda|liquidez|disponibilidad presupuestal|certificacion presupuestal|financiamiento",
    "materiales": r"falta de material|desabastec|no (hay|cuenta con|se cuenta con) material|escasez|abastecimiento",
    "equipo": r"maquinaria|equipo (inoperativo|malogrado|averiado)|falla mecanica",
    "personal": r"falta de personal|personal insuficiente|ausencia del (residente|especialista|ingeniero)|cambio de (residente|personal|especialista)",
    "expediente": r"deficiencia|incompatibilidad|error(es)? (en|del) (el )?expediente|expediente tecnico (deficiente|observado)|replanteo|discrepancia|vicios ocultos",
    "terreno": r"interferencia|libre disponibilidad|disponibilidad del terreno|saneamiento fisico|servidumbre|oposicion|conflicto social|pobladores|comuneros",
    "adicionales": r"adicional|deductivo|mayores metrados|prestacion(es)? adicional",
    "controversia": r"arbitraj|controversia|conciliacion|junta de (resolucion|prevencion) de disputas|reclamo",
    "incumplimiento": r"penalidad|incumpl|apercib|carta notarial|resolucion de(l)? contrato|intervencion economica",
    "calidad": r"no conform|observacion|rechaz|mala calidad|deficiente",
    "suspension": r"suspension|suspender|reinicio",
    "progreso": r"se (ejecuta|ejecutaron|viene ejecutando|continua)|avance (normal|conforme)|dentro del plazo|conforme a lo programado|adelantad",
}


def norm_text(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s)


def _panel() -> pd.DataFrame:
    return pd.read_parquet(FEATURES / "panel.parquet", columns=["cuaderno_id", "T"])


def build_lexicon(out: Path = FEATURES) -> Path:
    """Proporcion de asientos de la ventana con cada categoria (DuckDB, regex vectorizado)."""
    con = duckdb.connect()
    con.sql("set preserve_insertion_order=false")
    con.create_function("norm_text", norm_text, ["VARCHAR"], "VARCHAR")
    con.sql(f"create table panel as select cuaderno_id, \"T\"::date t from '{(out / 'panel.parquet').as_posix()}'")
    flags = ", ".join(f"regexp_matches(txt, '{rx}') as lx_{k}" for k, rx in LEXICON.items())
    con.sql(
        f"""
        create table asi as
        select cuaderno_id, fecha::date fecha, length(txt) len, {flags}
        from (select cuaderno_id, fecha, norm_text(coalesce(titulo,'') || ' ' || coalesce(descripcion,'')) txt
              from '{(CURATED / 'asiento.parquet').as_posix()}'
              where cuaderno_id in (select distinct cuaderno_id from panel))
        """
    )
    aggs = ", ".join(f"avg(lx_{k}::int) as txt_lx_{k}" for k in LEXICON)
    df = con.sql(
        f"""
        select p.cuaderno_id, p.t as "T", count(*) as txt_n_asientos_60d, avg(len) as txt_len_media_60d, {aggs}
        from panel p join asi a on a.cuaderno_id = p.cuaderno_id and a.fecha <= p.t and a.fecha > p.t - {WINDOW_DAYS}
        group by p.cuaderno_id, p.t
        """
    ).df()
    df["T"] = pd.to_datetime(df["T"])
    dst = out / "features_text_lexicon.parquet"
    df.to_parquet(dst, index=False)
    log.info("lexicon: %s", df.shape)
    return dst


def _window_matrix(panel: pd.DataFrame, asi: pd.DataFrame) -> sp.csr_matrix:
    """Matriz W (filas panel x asientos) con 1/n para asientos en la ventana (promedio)."""
    asi = asi.reset_index(drop=True)
    by_c = asi.groupby("cuaderno_id").indices
    rows, cols, vals = [], [], []
    fechas = asi["fecha"].to_numpy()
    for i, (cid, T) in enumerate(zip(panel["cuaderno_id"], panel["T"].to_numpy())):
        idx = by_c.get(cid)
        if idx is None:
            continue
        f = fechas[idx]
        sel = idx[(f <= T) & (f > T - np.timedelta64(WINDOW_DAYS, "D"))]
        if len(sel):
            rows += [i] * len(sel)
            cols += sel.tolist()
            vals += [1.0 / len(sel)] * len(sel)
    return sp.csr_matrix((vals, (rows, cols)), shape=(len(panel), len(asi)), dtype=np.float32)


def load_asientos_text(panel: pd.DataFrame) -> pd.DataFrame:
    con = duckdb.connect()
    return con.sql(
        f"""select cuaderno_id, fecha::timestamp fecha, coalesce(titulo,'') || ' . ' || coalesce(descripcion,'') txt
            from '{(CURATED / 'asiento.parquet').as_posix()}'
            where cuaderno_id in (select distinct cuaderno_id from panel) order by cuaderno_id, fecha"""
    ).df()


def build_lsa(out: Path = FEATURES, n_components: int = 64, seed: int = 42) -> Path:
    from sklearn.decomposition import TruncatedSVD
    from sklearn.feature_extraction.text import TfidfVectorizer

    panel = _panel()
    asi = load_asientos_text(panel)
    fit_mask = asi["fecha"] <= FIT_END
    vec = TfidfVectorizer(preprocessor=norm_text, ngram_range=(1, 2), min_df=30, max_df=0.5, max_features=60000,
                          sublinear_tf=True, dtype=np.float32, token_pattern=r"(?u)\b[a-z][a-z]+\b")
    rng = np.random.default_rng(seed)
    fit_idx = np.flatnonzero(fit_mask.to_numpy())
    fit_idx = rng.choice(fit_idx, size=min(400_000, len(fit_idx)), replace=False)
    vec.fit(asi["txt"].iloc[fit_idx])
    X = sp.vstack([vec.transform(asi["txt"].iloc[i : i + 200_000]) for i in range(0, len(asi), 200_000)]).tocsr()
    W = _window_matrix(panel, asi)
    Xw = W @ X
    svd = TruncatedSVD(n_components=n_components, random_state=seed)
    train_rows = (panel["T"] <= FIT_END).to_numpy()
    svd.fit(Xw[train_rows])
    Z = svd.transform(Xw)
    df = pd.DataFrame(Z, columns=[f"txt_lsa_{i:02d}" for i in range(n_components)])
    df.insert(0, "T", panel["T"].values)
    df.insert(0, "cuaderno_id", panel["cuaderno_id"].values)
    dst = out / "features_text_lsa.parquet"
    df.to_parquet(dst, index=False)
    import joblib

    joblib.dump({"vectorizer": vec, "svd": svd}, out / "text_lsa_model.joblib")
    sp.save_npz(out / "text_window_tfidf.npz", Xw.astype(np.float32))
    log.info("LSA: %s (varianza explicada %.3f)", df.shape, svd.explained_variance_ratio_.sum())
    return dst


def embed_asientos(model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                   out: Path = FEATURES, batch_size: int = 256, max_seq_length: int = 256) -> Path:
    """Embeddings por asiento (float16) en GPU si esta disponible. Cacheado en disco."""
    from sentence_transformers import SentenceTransformer

    dst = out / "asiento_embeddings.npy"
    idx_dst = out / "asiento_embeddings_index.parquet"
    panel = _panel()
    asi = load_asientos_text(panel)
    if dst.exists() and idx_dst.exists() and len(pd.read_parquet(idx_dst)) == len(asi):
        return dst
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer(model_name, device=device)
    if device == "cuda":
        model.half()  # fp16: ~2x mas rapido; los embeddings se guardan en float16 igualmente
    model.max_seq_length = max_seq_length
    texts = asi["txt"].map(lambda s: s[:2000]).tolist()
    E = model.encode(texts, batch_size=batch_size, show_progress_bar=False, convert_to_numpy=True, normalize_embeddings=True)
    np.save(dst, E.astype(np.float16))
    asi[["cuaderno_id", "fecha"]].to_parquet(idx_dst, index=False)
    log.info("embeddings %s con %s", E.shape, model_name)
    return dst


def build_emb(out: Path = FEATURES, n_components: int = 32, seed: int = 42) -> Path:
    from sklearn.decomposition import PCA

    panel = _panel()
    idx = pd.read_parquet(out / "asiento_embeddings_index.parquet")
    E = np.load(out / "asiento_embeddings.npy").astype(np.float32)
    W = _window_matrix(panel, idx)
    Ew = W @ E
    has = np.asarray(W.sum(axis=1)).ravel() > 0
    train_rows = ((panel["T"] <= FIT_END).to_numpy()) & has
    pca = PCA(n_components=n_components, random_state=seed).fit(Ew[train_rows])
    Z = pca.transform(Ew)
    Z[~has] = np.nan
    df = pd.DataFrame(Z, columns=[f"txt_emb_{i:02d}" for i in range(n_components)])
    df.insert(0, "T", panel["T"].values)
    df.insert(0, "cuaderno_id", panel["cuaderno_id"].values)
    dst = out / "features_text_emb.parquet"
    df.to_parquet(dst, index=False)
    np.save(out / "text_window_emb.npy", Ew.astype(np.float32))
    log.info("EMB: %s (varianza PCA %.3f)", df.shape, pca.explained_variance_ratio_.sum())
    return dst


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    if step in ("lexicon", "all"):
        build_lexicon()
    if step in ("lsa", "all"):
        build_lsa()
    if step in ("embed", "all"):
        embed_asientos()
    if step in ("emb", "all"):
        build_emb()
