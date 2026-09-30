import duckdb

con = duckdb.connect()
R = "data/raw/mef/"


def q(s):
    print(con.sql(s).df().to_string(max_colwidth=90))
    print()


o = "all_varchar=true,header=true"
con.sql(f"create view det as select * from read_csv('{R}DETALLE_INVERSIONES.csv',{o})")
con.sql(f"create view cie as select * from read_csv('{R}CIERRE_INVERSIONES.csv',{o})")
con.sql(
    "create view aqp_cui as select CODIGO_UNICO cui, FUNCION, 'ACTIVO' src from det where DEPARTAMENTO='AREQUIPA' union all select CODIGO_UNICO, FUNCION, 'CERRADO' from cie where DEPARTAMENTO='AREQUIPA'"
)
q("select src, count(*), count(distinct cui) from aqp_cui group by 1")
con.sql(f"create view ps as select * from read_csv('{R}PROCESO_SELECCION.csv',{o})")
q("select count(*) n, count(distinct CODIGO_UNICO) cui from ps")
q("select DES_ETAPA, count(*) from ps group by 1")
q("select length(PERIODO) l, count(*) n, min(PERIODO), max(PERIODO) from ps group by 1 order by 1")
con.sql("create table psa as select ps.* from ps join aqp_cui a on ps.CODIGO_UNICO=a.cui")
q("select count(*) n, count(distinct CODIGO_UNICO) cui from psa")
q(
    "select * from psa where CODIGO_UNICO=(select CODIGO_UNICO from psa where DES_ETAPA='EJECUCION' and length(PERIODO)=7 group by 1 having count(*)>20 limit 1) order by DES_PRODUCTO, DES_ETAPA, PERIODO limit 60"
)
con.sql(f"create view es as select * from read_csv('{R}ESTADO_SITUACIONAL.csv',{o})")
q("select count(*), count(distinct CODIGO_UNICO), min(FECHA_REGISTRO), max(FECHA_REGISTRO) from es")
q("select TIP_REGISTRO, COD_TIPO, count(*) from es group by 1,2")
con.sql("create table esa as select es.* from es join aqp_cui a on es.CODIGO_UNICO=a.cui")
q("select count(*), count(distinct CODIGO_UNICO), min(FECHA_REGISTRO), max(FECHA_REGISTRO) from esa")
q("select substr(FECHA_REGISTRO,1,4) y, count(*), count(distinct CODIGO_UNICO) from esa group by 1 order by 1")
q("select quantile_cont(n,[.25,.5,.75,.9]) from (select CODIGO_UNICO, count(*) n from esa group by 1)")
