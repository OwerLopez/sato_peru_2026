import logging, json, sys
from sato.models.experiment import Config, run
logging.basicConfig(level=logging.WARNING)
H=int(sys.argv[1]) if len(sys.argv)>1 else 60
out=[]
for fs,files,excl in [("A",(),()),("B_lex",("features_text_lexicon.parquet",),()),("B_lex_sinproxy",("features_text_lexicon.parquet",),("txt_lx_proxy_80",))]:
    r=run(Config(H=H,feature_set=fs,models=("lgbm",),extra_feature_files=files,exclude_prefixes=excl,n_boot=200))
    m=r['modelos']['lgbm']
    print(fs, 'AQP AP=%.3f ROC=%.3f | NAC AP=%.3f ROC=%.3f | valid AP=%.3f'%(m['arequipa']['pr_auc'],m['arequipa']['roc_auc'],m['nacional']['pr_auc'],m['nacional']['roc_auc'],m['valid_pr_auc']), flush=True)
