import duckdb, textwrap
con=duckdb.connect()
con.sql("create view asi as select * from 'data/staging/oece_asientos.parquet'")
def show(t,n=5,seed=1):
    df=con.sql(f"select TIPO_ASIENTO_REGISTRADO t, TIPO_USUARIO_REGISTRANTE u, FECHA_REGISTRO_ASIENTO f, TITULO_ASIENTO_REGISTRADO ti, DESCRIPCION_DEL_ASIENTO d from asi where TIPO_ASIENTO_REGISTRADO like '{t}%' using sample {n} rows (reservoir, {seed})").df()
    for r in df.itertuples(): print(f"[{r.t} | {r.u} | {r.f}] {r.ti}\n   ", textwrap.shorten(r.d or '',500)); 
    print('-----')
show('Valorizaci% menor al 80%',6)
show('Calendario acelerado',5)
show('Suspensi%n del plazo',4)
show('Resoluci%n de contrato',3)
# text-regex detection outside typed events
rx="(80\s*%|ochenta por ciento).{0,120}(programad)|calendario (de avance )?(de obra )?acelerado|atraso injustificado|retraso injustificado|intervenci.n econ.mica"
print(con.sql(f"""select TIPO_ASIENTO_REGISTRADO, count(*) n from asi where regexp_matches(lower(DESCRIPCION_DEL_ASIENTO||' '||TITULO_ASIENTO_REGISTRADO), '{rx}') group by 1 order by 2 desc limit 12""").df().to_string())
print(con.sql(f"""select count(distinct ID_CUADERNO) filter (where TIPO_ASIENTO_REGISTRADO like 'Valorizaci%menor al 80%' or TIPO_ASIENTO_REGISTRADO like 'Calendario acelerado%') typed,
 count(distinct ID_CUADERNO) filter (where regexp_matches(lower(DESCRIPCION_DEL_ASIENTO||' '||TITULO_ASIENTO_REGISTRADO), '{rx}')) textual,
 count(distinct ID_CUADERNO) filter (where TIPO_ASIENTO_REGISTRADO like 'Valorizaci%menor al 80%' or TIPO_ASIENTO_REGISTRADO like 'Calendario acelerado%' or regexp_matches(lower(DESCRIPCION_DEL_ASIENTO||' '||TITULO_ASIENTO_REGISTRADO), '{rx}')) union_
 from asi""").df())
