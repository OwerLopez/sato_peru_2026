import textwrap

import duckdb

con = duckdb.connect()
con.sql("create view asi as select * from 'data/staging/oece_asientos.parquet'")
con.sql("select setseed(0.42)")


def show(where, n=5):
    df = con.sql(
        f"select TIPO_ASIENTO_REGISTRADO t, TIPO_USUARIO_REGISTRANTE u, FECHA_REGISTRO_ASIENTO f, TITULO_ASIENTO_REGISTRADO ti, DESCRIPCION_DEL_ASIENTO d from asi where {where} order by random() limit {n}"
    ).df()
    for r in df.itertuples():
        print(f"[{r.t} | {r.u} | {r.f}] {r.ti}\n   ", textwrap.shorten(r.d or "", 420))
    print("-----")


show("TIPO_ASIENTO_REGISTRADO like 'Valorizaci%menor al 80%'", 6)
show("TIPO_ASIENTO_REGISTRADO like 'Calendario acelerado%'", 5)
show("TIPO_ASIENTO_REGISTRADO like 'Suspensi%n del plazo%'", 4)
show("TIPO_ASIENTO_REGISTRADO like 'Resoluci%n de contrato'", 3)
rx = r"(80\s*%|ochenta por ciento).{0,120}(programad)|calendario (de avance )?(de obra )?acelerado|atraso injustificado|retraso injustificado|intervenci.n econ.mica"
show(f"TIPO_ASIENTO_REGISTRADO='Otras ocurrencias' and regexp_matches(lower(DESCRIPCION_DEL_ASIENTO||' '||TITULO_ASIENTO_REGISTRADO), '{rx}')", 12)
