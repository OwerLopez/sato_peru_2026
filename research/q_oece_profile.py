import duckdb

con = duckdb.connect()
S = "data/staging/"


def q(s):
    print(con.sql(s).df().to_string(max_colwidth=80))
    print()


con.sql(f"create view cua as select * from '{S}oece_cuadernos.parquet'")
con.sql(f"create view asi as select * from '{S}oece_asientos.parquet'")
con.sql(f"create view val as select * from '{S}oece_valorizaciones.parquet'")
q(
    "select src_file, count(*) nrows, count(distinct NRO_CORRELATIVO_DE_CUADERNO_DE_OBRA) cuadernos, count(distinct IDENTIFICADOR_DEL_CONTRATO) contratos from cua group by 1"
)
q("select count(distinct NRO_CORRELATIVO_DE_CUADERNO_DE_OBRA) cuad_total, count(distinct IDENTIFICADOR_DEL_CONTRATO) contr from cua")
q(
    "select count(distinct NRO_CORRELATIVO_DE_CUADERNO_DE_OBRA) cuad_aqp, count(distinct IDENTIFICADOR_DEL_CONTRATO) contr_aqp from cua where UBIGEO like '04%'"
)
q(
    "select split_part(DESCRIPCION_DE_UBIGEO,',',2) prov, count(distinct NRO_CORRELATIVO_DE_CUADERNO_DE_OBRA) n from cua where UBIGEO like '04%' group by 1 order by 2 desc"
)
q("select nfiles, count(*) from (select NRO_CORRELATIVO_DE_CUADERNO_DE_OBRA c, count(distinct src_file) nfiles from cua group by 1) group by 1")
q(r"""select count(distinct NRO_CORRELATIVO_DE_CUADERNO_DE_OBRA) filter (where regexp_matches(upper(DENOMINACION_DE_LA_OBRA),'CUI|C.DIGO .NICO')) cui_mention,
         count(distinct NRO_CORRELATIVO_DE_CUADERNO_DE_OBRA) total from cua where UBIGEO like '04%'""")
q("select count(distinct ID_CUADERNO) cuad_with_asientos, count(*) n from asi")
q("""select count(distinct a.ID_CUADERNO) cuad_aqp_with_asientos, count(*) asientos_aqp from asi a
     where a.ID_CUADERNO in (select NRO_CORRELATIVO_DE_CUADERNO_DE_OBRA from cua where UBIGEO like '04%')""")
q("select count(distinct ID_CUADERNO) orphan_cuadernos from asi where ID_CUADERNO not in (select NRO_CORRELATIVO_DE_CUADERNO_DE_OBRA from cua)")
q("select TIPO_ASIENTO_REGISTRADO, count(*) n from asi group by 1 order by 2 desc limit 30")
q("select TIPO_USUARIO_REGISTRANTE, count(*) n from asi group by 1 order by 2 desc")
q("select ESTADO_ASIENTO, count(*) n from asi group by 1 order by 2 desc")
q("select count(distinct IDENTIFICADOR_DEL_CONTRATO) contratos_val, count(*) from val")
q(
    "select count(distinct IDENTIFICADOR_DEL_CONTRATO) contratos_val_aqp, count(*) from val where IDENTIFICADOR_DEL_CONTRATO in (select IDENTIFICADOR_DEL_CONTRATO from cua where UBIGEO like '04%')"
)
