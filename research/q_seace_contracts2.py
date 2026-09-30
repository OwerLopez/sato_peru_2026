import glob
import os

import pandas as pd

fr = [
    pd.read_excel(f, engine="calamine", dtype=str).assign(archivo=os.path.basename(f))
    for f in sorted(glob.glob("data/raw/seace/CONOSCE_CONTRATOS*.xlsx"))
]
c = pd.concat(fr, ignore_index=True)
c.to_parquet("data/staging/seace_contratos.parquet", index=False)
print(len(c), c.n_cod_contrato.nunique(), c.codigoconvocatoria.nunique())
print(c.groupby("archivo").fecha_suscripcion_contrato.agg(["min", "max", "count"]))
cu = pd.read_parquet("data/curated/cuaderno.parquet")
cu = cu[cu.tiene_metadatos]
for a, b in [
    ("contrato_id", "n_cod_contrato"),
    ("expediente_id", "codigoconvocatoria"),
    ("contrato_id", "codigo_contrato"),
    ("expediente_id", "n_cod_contrato"),
]:
    m = cu[a].astype(str).isin(set(c[b].dropna().astype(str)))
    print(f"{a} in {b}: {m.mean():.3f} ({m.sum()}/{len(cu)})  AQP: {m[cu.dep_code == '04'].mean():.3f}")
