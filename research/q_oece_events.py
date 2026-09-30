import duckdb

con = duckdb.connect()
S = "data/staging/"


def q(s):
    print(con.sql(s).df().to_string(max_colwidth=90))
    print()


con.sql(
    f"create view cua as select distinct NRO_CORRELATIVO_DE_CUADERNO_DE_OBRA cid, UBIGEO, IDENTIFICADOR_DEL_CONTRATO contrato, DENOMINACION_DE_LA_OBRA obra, RUC_ENTIDAD_CONTRATANTE ruc_ent, RAZON_SOCIAL_ENTIDAD_CONTRATANTE ent, RUC_CONTRATISTA ruc_con, src_file from '{S}oece_cuadernos.parquet'"
)
con.sql(f"create view asi as select *, strptime(FECHA_REGISTRO_ASIENTO,'%Y%m%d')::date f from '{S}oece_asientos.parquet'")
con.sql("create view aqp as select a.* from asi a join (select distinct cid from cua where UBIGEO like '04%') c on a.ID_CUADERNO=c.cid")
q("select TIPO_ASIENTO_REGISTRADO t, count(*) n, count(distinct ID_CUADERNO) cuad, min(f) desde, max(f) hasta from aqp group by 1 order by 2 desc")
q("select TIPO_ASIENTO_REGISTRADO t, min(f) desde, max(f) hasta, count(*) n from asi group by 1 order by 2")
q("select strftime(f,'%Y-%m') m, count(*) n, count(distinct ID_CUADERNO) cuad from aqp group by 1 order by 1")
q("select quantile_cont(n,[0.1,0.25,0.5,0.75,0.9]) q, avg(n) from (select ID_CUADERNO, count(*) n from aqp group by 1)")
q("select quantile_cont(l,[0.1,0.25,0.5,0.75,0.9]) q, avg(l) from (select length(DESCRIPCION_DEL_ASIENTO) l from aqp)")
