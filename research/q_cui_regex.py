import duckdb, re, pandas as pd, unicodedata
con=duckdb.connect()
R='data/raw/mef/'; S='data/staging/'
o="all_varchar=true,header=true"
# MEF universe: CUI and SNIP
con.sql(f"""create table mef as
 select CODIGO_UNICO cui, CODIGO_SNIP snip, NOMBRE_INVERSION nombre, FUNCION funcion, DEPARTAMENTO dep, 'ACTIVO' src from read_csv('{R}DETALLE_INVERSIONES.csv',{o})
 union all select CODIGO_UNICO, CODIGO_SNIP, NOMBRE_INVERSION, FUNCION, DEPARTAMENTO, 'CERRADO' from read_csv('{R}CIERRE_INVERSIONES.csv',{o})
 union all select CODIGO_UNICO, COD_SNIP, NOMBRE_INVERSION, FUNCION, DEPARTAMENTO, 'DESACTIVADO' from read_csv('{R}INVERSIONES_DESACTIVADAS.csv',{o})""")
print(con.sql("select src, count(*), count(distinct cui) from mef group by 1").df())
cuis=set(con.sql("select distinct cui from mef where cui is not null and cui<>''").df().cui)
snip2cui=dict(con.sql("select snip, min(cui) from mef where snip is not null and snip not in ('','0') and cui<>'' group by 1 having count(distinct cui)=1").fetchall())
cua=con.sql(f"select distinct NRO_CORRELATIVO_DE_CUADERNO_DE_OBRA cid, UBIGEO, DENOMINACION_DE_LA_OBRA obra from '{S}oece_cuadernos.parquet'").df()
def strip(s): return unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().upper()
RX_CUI=re.compile(r'(?:C\.?\s*U\.?\s*I\.?|CODIGO\s+UNICO(?:\s+DE\s+INVERSION(?:ES)?)?|COD\.?\s*UNICO)\s*(?:N\s*[O°º]?\.?|NRO\.?|NUMERO)?\s*[:\-\.]?\s*(\d{6,7})')
RX_SNIP=re.compile(r'SNIP\s*(?:N\s*[O°º]?\.?|NRO\.?)?\s*[:\-\.]?\s*(\d{4,7})')
RX_ANY7=re.compile(r'\b(2\d{6})\b')
rows=[]
for r in cua.itertuples():
    t=strip(r.obra or '')
    c=RX_CUI.findall(t); s=RX_SNIP.findall(t); a=RX_ANY7.findall(t)
    cand=[x for x in c if x in cuis]
    how=None
    if cand: how='regex_cui'
    elif s and any(x in snip2cui for x in s): cand=[snip2cui[x] for x in s if x in snip2cui]; how='regex_snip'
    elif a and any(x in cuis for x in a): cand=[x for x in a if x in cuis]; how='bare_7digit'
    rows.append((r.cid,r.UBIGEO,bool(c),bool(s),how,len(set(cand)),cand[0] if cand else None, c[0] if c else None))
d=pd.DataFrame(rows,columns=['cid','ubigeo','has_cui_kw','has_snip_kw','how','ncand','cui','raw_cui'])
d['aqp']=d.ubigeo.fillna('').str.startswith('04')
for lab,g in [('NACIONAL',d),('AREQUIPA',d[d.aqp])]:
    print('==',lab,'cuadernos',len(g))
    print(g.how.value_counts(dropna=False).to_string())
    print('kw_cui present but not in MEF:', ((g.has_cui_kw)&(g.how.isna())).sum(), ' ambiguous(>1 cand):',(g.ncand>1).sum())
d.to_parquet('data/staging/er_regex_cuaderno_cui.parquet',index=False)
# sample of failures in AQP
print(d[(d.aqp)&(d.has_cui_kw)&(d.how.isna())].merge(cua,on='cid').obra.head(8).to_string())
