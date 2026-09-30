import logging
import sys

from sato.models.experiment import Config, run

logging.basicConfig(level=logging.WARNING)
H = int(sys.argv[1]) if len(sys.argv) > 1 else 60
for fs, files, stack in [
    ("B_lsa", ("features_text_lsa.parquet",), ()),
    ("B_stack", (), ("text_window_tfidf.npz",)),
    ("B_lex_stack", ("features_text_lexicon.parquet",), ("text_window_tfidf.npz",)),
]:
    r = run(Config(H=H, feature_set=fs, models=("lgbm",), extra_feature_files=files, text_stack=stack, n_boot=200))
    m = r["modelos"]["lgbm"]
    print(
        fs,
        "AQP AP={:.3f} ROC={:.3f} | NAC AP={:.3f} ROC={:.3f} | valid AP={:.3f}".format(m["arequipa"]["pr_auc"], m["arequipa"]["roc_auc"], m["nacional"]["pr_auc"], m["nacional"]["roc_auc"], m["valid_pr_auc"]),
        flush=True,
    )
