import pandas as pd, glob, duckdb, os
fr=[]
for f in sorted(glob.glob('data/raw/seace/CONOSCE_CONTRATOS*.xlsx')):
    x=pd.ExcelFile(f,engine='calamine')
    for s in x.sheet_names:
        d=x.parse(s,dtype=str); d['archivo']=os.path.basename(f); d['hoja']=s; fr.append(d)
    print(f, x.sheet_names, sum(len(z) for z in fr[-len(x.sheet_names):]), list(fr[-1].columns)[:30])
c=pd.concat(fr,ignore_index=True)
print(len(c), c.N_COD_CONTRATO.nunique() if 'N_COD_CONTRATO' in c else None)
cu=pd.read_parquet('data/curated/cuaderno.parquet')
ids=set(c.get('N_COD_CONTRATO',pd.Series(dtype=str)).dropna().astype(str))
cu_ids=cu.contrato_id.dropna().astype(str)
print('cuadernos contrato_id in CONOSCE N_COD_CONTRATO:', cu_ids.isin(ids).mean(), cu_ids.isin(ids).sum(), len(cu_ids))
if 'CODIGOCONVOCATORIA' in c: 
    print('expediente in CODIGOCONVOCATORIA:', cu.expediente_id.dropna().astype(str).isin(set(c.CODIGOCONVOCATORIA.dropna().astype(str))).mean())
print(c.head(3).T.to_string()[:3000])
