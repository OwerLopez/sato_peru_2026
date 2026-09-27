from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from sato.api import db
from sato.api.security import require_role

router = APIRouter(tags=["estadisticas e investigacion"])


@router.get("/estadisticas/resumen")
def resumen():
    corte = db.one("select max(fecha_corte) f from prediccion where tipo = 'vigente'")["f"]
    kpi = db.one(
        """select count(*) obras, count(*) filter (where estado_observado = 'EN_EJECUCION') en_ejecucion,
                  count(*) filter (where fecha_atraso is not null) con_atraso_normativo,
                  count(*) filter (where cui is not null) con_cui, count(distinct provincia) provincias,
                  (select count(*) from asiento) asientos
           from obra"""
    )
    vig = db.one(
        """select count(*) evaluadas, count(*) filter (where alerta) alertas, count(*) filter (where nivel = 'ALTO') alto,
                  count(*) filter (where nivel = 'MEDIO') medio
           from prediccion p join modelo m on m.id = p.modelo_id and m.activo where p.fecha_corte = :c""",
        c=corte,
    )
    prov = db.rows(
        """select o.provincia, count(*) obras, count(*) filter (where o.estado_observado = 'EN_EJECUCION') en_ejecucion,
                  count(*) filter (where o.fecha_atraso is not null) con_atraso,
                  count(p.id) filter (where p.alerta) alertas_vigentes
           from obra o left join prediccion p on p.cuaderno_id = o.cuaderno_id and p.fecha_corte = :c
           group by 1 order by 2 desc""",
        c=corte,
    )
    sector = db.rows(
        """select o.sector, count(*) obras, count(*) filter (where o.fecha_atraso is not null) con_atraso,
                  count(p.id) filter (where p.alerta) alertas_vigentes
           from obra o left join prediccion p on p.cuaderno_id = o.cuaderno_id and p.fecha_corte = :c
           group by 1 order by 2 desc""",
        c=corte,
    )
    historico = db.rows(
        """select p.fecha_corte, count(*) evaluadas, count(*) filter (where p.alerta) alertas,
                  count(*) filter (where p.alerta and p.y_observado = 1) alertas_confirmadas,
                  count(*) filter (where p.y_observado = 1) eventos_observados,
                  count(*) filter (where p.y_observado is not null) observables
           from prediccion p join modelo m on m.id = p.modelo_id and m.activo group by 1 order by 1"""
    )
    return {"fecha_corte": corte, "kpi": kpi, "vigente": vig, "por_provincia": prov, "por_sector": sector, "historico": historico}


@router.get("/modelo")
def modelo():
    return db.one("select id, nombre, version, objetivo, horizonte_dias, conjunto_features, algoritmo, entrenado_hasta, entrenado_en, umbral_alerta, metricas, features, sha256 from modelo where activo")


@router.get("/investigacion/experimentos")
def experimentos(objetivo: str = Query("atraso", max_length=20), alcance_test: str = Query("arequipa", max_length=20)):
    return db.rows(
        """select objetivo, horizonte, conjunto_features, alcance_entrenamiento, modelo, alcance_test, metricas
           from experimento_resultado where objetivo = :o and alcance_test = :t order by horizonte, conjunto_features, modelo""",
        o=objetivo, t=alcance_test,
    )


@router.get("/investigacion/comparacion")
def comparacion(objetivo: str = Query("atraso", max_length=20)):
    return db.rows("select * from comparacion_ab where objetivo = :o order by horizonte, alcance_test, metrica, variante", o=objetivo)


@router.get("/fuentes")
def fuentes():
    return {
        "corte": db.one("select fecha_corte, generado_en, descripcion from corte_datos order by id desc limit 1"),
        "archivos": db.rows("select fuente, url, ruta, bytes, sha256, last_modified, descargado_en from fuente_archivo order by fuente, ruta"),
        "cobertura": db.one(
            """select (select count(*) from obra) obras, (select count(*) from obra where cui is not null) obras_con_cui,
                      (select count(*) from obra where codigo_infobras is not null) obras_con_infobras,
                      (select count(*) from obra where url_contrato_seace is not null) obras_con_contrato_seace,
                      (select count(*) from obra where historia_completa) obras_historia_completa,
                      (select count(distinct cui) from siaf_mensual) inversiones_con_siaf,
                      (select count(*) from contraloria_paralizada) registros_contraloria"""
        ),
    }


@router.get("/admin/auditoria")
def auditoria(limite: int = Query(100, ge=1, le=1000), _u: dict = Depends(require_role("admin"))):
    return db.rows("select a.ts, a.accion, a.recurso, a.detalle, a.ip::text ip, u.email from auditoria a left join usuario u on u.id = a.usuario_id order by a.ts desc limit :l", l=limite)


@router.get("/modelo/cartera")
def modelo_cartera():
    """Ficha de los modelos de cartera (inicio y seguimiento): umbrales, calibracion por nivel y metricas de test."""
    r = db.one("select valor from configuracion where clave = 'modelo_cartera'")
    return r["valor"] if r else None


@router.get("/investigacion/sectores")
def desempeno_sectores():
    """Desempeno de cada modelo por sector o tipo de obra en su prueba temporal (IC 95 % por bootstrap de obras)."""
    r = db.one("select valor from configuracion where clave = 'desempeno_sectores'")
    return r["valor"] if r else None


@router.get("/modelo/calibracion")
def calibracion():
    """Confiabilidad de las probabilidades: tasa de atraso OBSERVADA por nivel y por decil de riesgo en el backtest as-of
    (predicciones emitidas cada mes solo con informacion anterior y ya contrastadas con lo ocurrido)."""
    base = db.one(
        """select count(*) n, avg(y_observado::float) tasa_base, min(fecha_corte) desde, max(fecha_corte) hasta
           from prediccion p join modelo m on m.id = p.modelo_id and m.activo where p.tipo = 'backtest' and p.y_observado is not null""")
    niveles = db.rows(
        """select nivel, count(*) n, avg(score) probabilidad_media, avg(y_observado::float) tasa_observada, sum(y_observado) eventos
           from prediccion p join modelo m on m.id = p.modelo_id and m.activo where p.tipo = 'backtest' and p.y_observado is not null
           group by 1 order by 3 desc""")
    deciles = db.rows(
        """select decil, count(*) n, avg(score) probabilidad_media, avg(y::float) tasa_observada from (
             select score, y_observado y, ntile(10) over (order by score) decil
             from prediccion p join modelo m on m.id = p.modelo_id and m.activo where p.tipo = 'backtest' and p.y_observado is not null) x
           group by 1 order by 1""")
    card = (db.one("select valor from configuracion where clave = 'modelo_cartera'") or {}).get("valor") or {}
    cartera = {t: {"tasa_base": u.get("tasa_base_test"), "desde": u.get("periodo_test_desde"),
                   "niveles": [{"nivel": n, **v} for n, v in (u.get("tasa_por_nivel_test") or {}).items()]}
               for t, u in (card.get("umbrales") or {}).items()}
    return {"alerta_60d": {**(base or {}), "niveles": niveles, "deciles": deciles}, "cartera": cartera}
