"""Importancia global TreeSHAP del modelo B_full (H=60, entrenamiento nacional) sobre el TEST temporal.

Salida: docs/research/importancia_global.csv (por feature) e importancia_grupos.csv (por grupo).
"""

import joblib
import numpy as np
import pandas as pd

from sato.config import ARTIFACTS, ROOT
from sato.models.experiment import Config, asof_text_scores, load_dataset, splits
from sato.models.grid import FEATURE_SETS
from sato.serving.descriptions import describe, group_of

H, FS = 60, "B_full"
cfg = Config(H=H, feature_set=FS, **FEATURE_SETS[FS])
df, cols = load_dataset(cfg)
for wf in cfg.text_stack:
    name = "txt_stack_" + ("tfidf" if wf.endswith(".npz") else "emb")
    df[name] = asof_text_scores(df, H, window_file=wf)
    cols.append(name)
_, _, _, test = splits(df, H)
art = joblib.load(ARTIFACTS / "experiments" / f"atraso_H{H}_{FS}_train-nacional" / "model_lgbm.joblib")
m = art["model"]
assert list(art["features"]) == cols, "las columnas no coinciden con el modelo guardado"
out = []
for scope, mask in (("nacional", test), ("arequipa", test & (df["dep_code"] == "04"))):
    S = m.booster_.predict(df.loc[mask, cols], pred_contrib=True)[:, :-1]
    imp = pd.DataFrame({"feature": cols, "mean_abs_shap": np.abs(S).mean(axis=0), "mean_shap": S.mean(axis=0)})
    imp["grupo"] = imp["feature"].map(group_of)
    imp["alcance"] = scope
    imp["descripcion"] = imp["feature"].map(lambda f: describe(f, None).split(":")[0])
    out.append(imp)
imp = pd.concat(out)
imp["share"] = imp["mean_abs_shap"] / imp.groupby("alcance")["mean_abs_shap"].transform("sum")
d = ROOT / "docs" / "research"
imp.sort_values(["alcance", "mean_abs_shap"], ascending=[True, False]).to_csv(d / "importancia_global.csv", index=False)
g = imp.groupby(["alcance", "grupo"])["share"].sum().unstack(0).sort_values("nacional", ascending=False)
g.to_csv(d / "importancia_grupos.csv")
print(g.round(3).to_string())
print(
    imp[imp.alcance == "nacional"]
    .sort_values("mean_abs_shap", ascending=False)
    .head(20)[["feature", "grupo", "share", "mean_abs_shap"]]
    .round(4)
    .to_string()
)
