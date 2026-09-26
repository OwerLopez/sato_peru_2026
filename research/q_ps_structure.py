import duckdb
con=duckdb.connect()
R='data/raw/mef/'
def q(s): print(con.sql(s).df().to_string(max_colwidth=60)); print()
o="all_varchar=true,header=true"
con.sql(f"create view det as select * from read_csv('{R}DETALLE_INVERSIONES.csv',{o})")
con.sql(f"create view cie as select * from read_csv('{R}CIERRE_INVERSIONES.csv',{o})")
con.sql("create table aqp as select CODIGO_UNICO cui, FUNCION, 'ACTIVO' src from det where DEPARTAMENTO='AREQUIPA' union all select CODIGO_UNICO, FUNCION, 'CERRADO' from cie where DEPARTAMENTO='AREQUIPA'")
con.sql(f"create table psa as select ps.* from read_csv('{R}PROCESO_SELECCION.csv',{o}) ps where CODIGO_UNICO in (select cui from aqp)")
con.sql("copy psa to 'data/staging/mef_componentes_aqp.parquet' (format parquet)")
q("select DES_ETAPA, (DES_ACCION is null) agg_row, regexp_matches(PERIODO,'^\d{4}-\d{2}$') ym, count(*), count(distinct CODIGO_UNICO) cui from psa group by all order by 1,2,3")
# per CUI monthly series
con.sql("""create table ser as select CODIGO_UNICO cui, DES_ETAPA etapa, PERIODO per, sum(try_cast(VALORIZ_ACUM as double)) val, max(try_cast(AVANCE as double)) av, count(*) nrows
 from psa where DES_ACCION is null and regexp_matches(PERIODO,'^\d{4}-\d{2}$') and DES_ETAPA in ('EJECUCION','CONTRACTUAL') group by all""")
q("select etapa, count(distinct cui), count(*), min(per), max(per) from ser group by 1")
q("""with e as (select cui, count(*) ne from ser where etapa='EJECUCION' group by 1), c as (select cui, count(*) nc from ser where etapa='CONTRACTUAL' group by 1)
select count(*) both_cui, quantile_cont(ne,[.25,.5,.75]) ne_q, quantile_cont(nc,[.25,.5,.75]) nc_q from e join c using(cui)""")
q("select substr(per,1,4) y, etapa, count(distinct cui) from ser group by 1,2 order by 1,2")
q("""select a.FUNCION, count(distinct s.cui) cui_with_exec_contract from ser s join aqp a on a.cui=s.cui
     where s.cui in (select cui from ser where etapa='CONTRACTUAL') and s.cui in (select cui from ser where etapa='EJECUCION') group by 1 order by 2 desc""")
q("select * from psa where CODIGO_UNICO='2150975' and DES_ETAPA='CRONOGRAMA' limit 12")
q("select DES_ETAPA, PERIODO, count(*) from psa where DES_ETAPA in ('CRONOGRAMA','FYE','CONSISTENCIA') group by all order by 3 desc limit 15")
