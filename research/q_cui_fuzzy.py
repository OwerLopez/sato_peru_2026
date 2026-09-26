import duckdb, re, pandas as pd, numpy as np, unicodedata
from sklearn.feature_extraction.text import TfidfVectorizer
con=duckdb.connect()
R='data/raw/mef/'; S='data/staging/'
o="all_varchar=true,header=true"
mef=con.sql(f"""
 select CODIGO_UNICO cui, NOMBRE_INVERSION nombre, UBIGEO ubigeo from read_csv('{R}DETALLE_INVERSIONES.csv',{o})
 union all select CODIGO_UNICO, NOMBRE_INVERSION, UBIGEO from read_csv('{R}CIERRE_INVERSIONES.csv',{o})
 union all select CODIGO_UNICO, NOMBRE_INVERSION, UBIGEO from read_csv('{R}INVERSIONES_DESACTIVADAS.csv',{o})""").df()
mef=mef[mef.cui.notna()&(mef.cui!='')].drop_duplicates('cui')
mef['dep']=mef.ubigeo.fillna('').str.zfill(6).str[:2]
cua=con.sql(f"select distinct NRO_CORRELATIVO_DE_CUADERNO_DE_OBRA cid, UBIGEO ubigeo, DENOMINACION_DE_LA_OBRA obra from '{S}oece_cuadernos.parquet'").df()
cua['dep']=cua.ubigeo.fillna('').str[:2]
rx=pd.read_parquet('data/staging/er_regex_cuaderno_cui.parquet')[['cid','how','cui']]
def norm(s):
    s=unicodedata.normalize('NFKD',s if isinstance(s,str) else '').encode('ascii','ignore').decode().upper()
    s=re.sub(r'(C\.?U\.?I\.?|CODIGO UNICO[A-Z ]*|SNIP)\s*(N[O°]?\.?|NRO\.?)?\s*[:\-]?\s*\d+','',s)
    s=re.sub(r'^.*?(EJECUCION DE (LA )?(OBRA|SALDO DE OBRA)[: ]*|CONTRATACION DE[A-Z ]*?OBRA[: ]*)','',s)
    s=re.sub(r'[^A-Z0-9 ]',' ',s); return re.sub(r'\s+',' ',s).strip()
mef['n']=mef.nombre.map(norm); cua['n']=cua.obra.map(norm)
out=[]
for dep,g in cua.groupby('dep'):
    m=mef[mef.dep==dep]
    if m.empty or not dep: 
        for r in g.itertuples(): out.append((r.cid,None,0,0)); 
        continue
    v=TfidfVectorizer(analyzer='char_wb',ngram_range=(3,5),min_df=1,sublinear_tf=True).fit(pd.concat([m.n,g.n]))
    A=v.transform(g.n); B=v.transform(m.n)
    for i in range(0,A.shape[0],500):
        sim=(A[i:i+500]@B.T).toarray()
        top=np.argsort(-sim,axis=1)[:,:2]
        for j,row in enumerate(top):
            s1=sim[j,row[0]]; s2=sim[j,row[1]] if len(row)>1 else 0
            out.append((g.cid.iloc[i+j], m.cui.iloc[row[0]], s1, s1-s2))
f=pd.DataFrame(out,columns=['cid','cui_fz','score','margin']).merge(rx,on='cid',how='left')
f.to_parquet('data/staging/er_fuzzy_cuaderno_cui.parquet',index=False)
gt=f[f.how=='regex_cui']
print('ground-truth pairs',len(gt))
for th in [0.5,0.6,0.7,0.75,0.8,0.85,0.9]:
    for mg in [0.0,0.05,0.1]:
        sel=gt[(gt.score>=th)&(gt.margin>=mg)]
        prec=(sel.cui_fz==sel.cui).mean() if len(sel) else np.nan
        print(f'th={th} margin>={mg}: coverage={len(sel)/len(gt):.3f} precision={prec:.3f}')
