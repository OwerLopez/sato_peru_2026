import pandas as pd, glob, re, os
fs=sorted(f for f in glob.glob('data/raw/contraloria/*') if re.search(r'anexo-n-0?2-(base|reporte)|anexo-n-01-base-de-datos-con-la-lista',f,re.I))
for f in fs:
    x=pd.ExcelFile(f,engine='calamine')
    df=x.parse(x.sheet_names[0],header=None,nrows=15)
    hr=next(i for i in range(15) if df.iloc[i].notna().sum()>8)
    d=x.parse(x.sheet_names[0],header=hr)
    cols=[str(c) for c in d.columns]
    depc=[c for c in cols if 'DEPART' in c.upper()]
    aq=(d[depc[0]].astype(str).str.upper().str.contains('AREQUIPA')).sum() if depc else None
    print(os.path.basename(f)[:75], x.sheet_names[:3], 'hdr',hr,'rows',len(d),'AQP',aq)
    print('   ',cols[:45])
