"""Radar de obras ACTIVAS (prediccion a futuro), resumen ejecutivo y comparador regional.

Dos modelos complementarios, ambos sobre obras en ejecucion:
  * `cuaderno`: contratos con cuaderno de obra digital; probabilidad de incurrir en la causal del 80 %
    (RLCE art. 203 / RLGCP art. 207) en los proximos 60 dias.
  * `cartera` : obras INFOBRAS de cualquier modalidad; probabilidad de terminar con retraso significativo
    (fin real > fin programado + 30 % del plazo).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Path, Query

from sato.api import db
from sato.api.cache import cacheado

router = APIRouter(tags=["radar"])

# riesgo vigente de cada obra de la cartera (vista materializada que se refresca en cada carga)
CART_LAST = " left join cartera_riesgo_vigente lr on lr.codigo_infobras = c.codigo_infobras "


@router.get("/radar/cuaderno")
@cacheado
def radar_cuaderno(departamento: str | None = None, provincia: str | None = None, sector: str | None = None,
                   nivel: Literal["ALTO", "MEDIO", "BAJO"] | None = None, limite: int = Query(200, ge=1, le=1000)):
    corte = (db.one("select max(fecha_corte) f from prediccion where tipo = 'vigente'") or {}).get("f")
    h = (db.one("select horizonte_dias h from modelo where activo") or {}).get("h")
    items = db.rows(
        """select p.id prediccion_id, p.fecha_corte, p.score, p.nivel, p.percentil,
                  o.cuaderno_id, o.denominacion nombre, o.departamento, o.provincia, o.distrito, o.sector, o.cui,
                  coalesce(o.monto_contrato, i.monto_viable) monto, e.nombre entidad, o.primer_asiento, o.n_asientos,
                  (select json_agg(json_build_object('descripcion', x.descripcion, 'shap', x.shap) order by x.shap desc)
                     from (select * from explicacion where prediccion_id = p.id and shap > 0 order by shap desc limit 3) x) factores
           from prediccion p join modelo m on m.id = p.modelo_id and m.activo
           join obra o on o.cuaderno_id = p.cuaderno_id left join entidad e on e.ruc = o.entidad_ruc left join inversion i on i.cui = o.cui
           where p.fecha_corte = :corte and p.tipo = 'vigente'
             and (cast(:dep as text) is null or o.departamento = :dep) and (cast(:prov as text) is null or o.provincia = :prov)
             and (cast(:sector as text) is null or o.sector = :sector) and (cast(:nivel as text) is null or p.nivel = :nivel)
           order by p.score desc limit :lim""",
        corte=corte, dep=departamento, prov=provincia, sector=sector, nivel=nivel, lim=limite)
    return {"fecha_corte": corte, "horizonte_dias": h, "items": items}


@router.get("/radar/cartera")
@cacheado
def radar_cartera(departamento: str | None = None, provincia: str | None = None, tipo_obra: str | None = None,
                  modalidad: str | None = None, nivel: Literal["ALTO", "MEDIO", "BAJO"] | None = None,
                  limite: int = Query(200, ge=1, le=1000)):
    items = db.rows(
        f"""select c.codigo_infobras, c.nombre, c.departamento, c.provincia, c.distrito, c.tipo_obra, c.modalidad, c.costo monto,
                   c.entidad, c.fecha_inicio, c.fin_programado, c.plazo_dias, c.cuaderno_id,
                   lr.riesgo_id, lr.modelo, lr.fecha_corte, lr.score, lr.nivel,
                   (select json_agg(json_build_object('descripcion', x.descripcion, 'shap', x.shap) order by x.shap desc)
                      from (select * from cartera_explicacion where riesgo_id = lr.riesgo_id and shap > 0 order by shap desc limit 3) x) factores
            from cartera_obra c {CART_LAST}
            where c.estado_operativo = 'ACTIVA' and lr.riesgo_id is not null
              and (cast(:dep as text) is null or c.departamento = :dep) and (cast(:prov as text) is null or c.provincia = :prov)
              and (cast(:tipo as text) is null or c.tipo_obra = :tipo) and (cast(:mod as text) is null or c.modalidad = :mod)
              and (cast(:nivel as text) is null or lr.nivel = :nivel)
            order by lr.score desc limit :lim""",
        dep=departamento, prov=provincia, tipo=tipo_obra, mod=modalidad, nivel=nivel, lim=limite)
    return {"items": items}


@router.get("/resumen")
@cacheado
def resumen(departamento: str | None = None):
    """Indicadores del centro de comando para el ambito seleccionado."""
    dep = departamento
    corte = (db.one("select max(fecha_corte) f from prediccion where tipo = 'vigente'") or {}).get("f")
    cua = db.one(
        """select count(*) activas, count(*) filter (where p.nivel = 'ALTO') alto, count(*) filter (where p.nivel = 'MEDIO') medio,
                  sum(coalesce(o.monto_contrato, i.monto_viable)) monto_activo,
                  sum(coalesce(o.monto_contrato, i.monto_viable)) filter (where p.nivel = 'ALTO') monto_alto
           from prediccion p join modelo m on m.id = p.modelo_id and m.activo join obra o on o.cuaderno_id = p.cuaderno_id
           left join inversion i on i.cui = o.cui
           where p.fecha_corte = :corte and p.tipo = 'vigente' and (cast(:dep as text) is null or o.departamento = :dep)""",
        corte=corte, dep=dep)
    car = db.one(
        f"""select count(*) activas, count(*) filter (where lr.nivel = 'ALTO') alto, count(*) filter (where lr.nivel = 'MEDIO') medio,
                   sum(c.costo) monto_activo, sum(c.costo) filter (where lr.nivel = 'ALTO') monto_alto,
                   count(*) filter (where c.cuaderno_id is not null) con_cuaderno
            from cartera_obra c {CART_LAST}
            where c.estado_operativo = 'ACTIVA' and (cast(:dep as text) is null or c.departamento = :dep)""", dep=dep)
    # Consolidado sin doble conteo: una obra evaluada por ambos modelos (cartera enlazada a un cuaderno vigente) se cuenta
    # una sola vez; el monto usa el del contrato del cuaderno cuando existe; "alto" = nivel ALTO en cualquiera de los modelos.
    con = db.one(
        f"""with v as (
              select o.cuaderno_id, coalesce(o.monto_contrato, i.monto_viable) monto, p.nivel
              from prediccion p join modelo m on m.id = p.modelo_id and m.activo join obra o on o.cuaderno_id = p.cuaderno_id
              left join inversion i on i.cui = o.cui
              where p.fecha_corte = :corte and p.tipo = 'vigente' and (cast(:dep as text) is null or o.departamento = :dep)),
            c as (
              select distinct on (coalesce(c.cuaderno_id::text, c.codigo_infobras)) c.cuaderno_id, c.costo, lr.nivel
              from cartera_obra c {CART_LAST}
              where c.estado_operativo = 'ACTIVA' and (cast(:dep as text) is null or c.departamento = :dep)
              order by coalesce(c.cuaderno_id::text, c.codigo_infobras), lr.score desc nulls last)
            select count(*) obras, count(*) filter (where v.cuaderno_id is not null and c.nivel is not null) en_ambos,
                   sum(coalesce(v.monto, c.costo)) monto,
                   count(*) filter (where v.nivel = 'ALTO' or c.nivel = 'ALTO') alto,
                   sum(coalesce(v.monto, c.costo)) filter (where v.nivel = 'ALTO' or c.nivel = 'ALTO') monto_alto
            from v full outer join c on c.cuaderno_id = v.cuaderno_id""", corte=corte, dep=dep)
    otros = db.one(
        """select count(*) filter (where estado_operativo = 'CONSUMADO') consumado, count(*) filter (where estado_operativo = 'DESACTUALIZADA') desactualizada,
                  count(*) filter (where estado_operativo = 'FINALIZADA') finalizadas,
                  avg(retraso_significativo::float) filter (where retraso_significativo is not null) tasa_historica
           from cartera_obra where (cast(:dep as text) is null or departamento = :dep)""", dep=dep)
    dist = db.rows(
        """select coalesce(o.provincia, 'SIN DATO') ambito, count(*) evaluadas, count(*) filter (where p.nivel = 'ALTO') alto
           from prediccion p join modelo m on m.id = p.modelo_id and m.activo join obra o on o.cuaderno_id = p.cuaderno_id
           where p.fecha_corte = :corte and p.tipo = 'vigente' and (cast(:dep as text) is not null and o.departamento = :dep)
           group by 1
           union all
           select coalesce(o.departamento, 'SIN DATO'), count(*), count(*) filter (where p.nivel = 'ALTO')
           from prediccion p join modelo m on m.id = p.modelo_id and m.activo join obra o on o.cuaderno_id = p.cuaderno_id
           where p.fecha_corte = :corte and p.tipo = 'vigente' and cast(:dep as text) is null
           group by 1 order by 2 desc""", corte=corte, dep=dep)
    hist = db.rows(
        """select p.fecha_corte, count(*) evaluadas, count(*) filter (where p.alerta) alertas,
                  count(*) filter (where p.alerta and p.y_observado = 1) alertas_confirmadas,
                  count(*) filter (where p.y_observado = 1) eventos_observados,
                  count(*) filter (where p.y_observado is not null) observables
           from prediccion p join modelo m on m.id = p.modelo_id and m.activo join obra o on o.cuaderno_id = p.cuaderno_id
           where (cast(:dep as text) is null or o.departamento = :dep) group by 1 order by 1""", dep=dep)
    card = (db.one("select valor->>'obs_end' f from configuracion where clave = 'modelo_cartera'") or {}).get("f")
    return {"fecha_corte_cuaderno": corte, "fecha_corte_cartera": card, "departamento": dep, "cuaderno": cua, "cartera": car, "consolidado": con, "cartera_otros": otros,
            "distribucion": dist, "historico": hist}


@router.get("/comparador")
@cacheado
def comparador(por: Literal["departamento", "sector"] = "departamento"):
    """Benchmarking territorial y sectorial con datos observados y predicciones vigentes."""
    if por == "departamento":
        key_c, key_o = "c.departamento", "o.departamento"
    else:
        key_c, key_o = "c.tipo_obra", "o.sector"
    cart = db.rows(
        f"""select {key_c} clave, count(*) obras,
                   avg(c.retraso_significativo::float) filter (where c.retraso_significativo is not null) tasa_retraso_historica,
                   count(*) filter (where c.retraso_significativo is not null) obras_con_resultado,
                   count(*) filter (where c.estado_operativo = 'ACTIVA') activas,
                   count(*) filter (where c.estado_operativo = 'ACTIVA' and lr.nivel = 'ALTO') activas_alto,
                   sum(c.costo) filter (where c.estado_operativo = 'ACTIVA') monto_activo
            from cartera_obra c {CART_LAST} where {key_c} is not null group by 1""")
    corte = (db.one("select max(fecha_corte) f from prediccion where tipo = 'vigente'") or {}).get("f")
    cua = {r["clave"]: r for r in db.rows(
        f"""select {key_o} clave, count(*) evaluadas, count(*) filter (where p.nivel = 'ALTO') alto, avg(p.score) riesgo_medio
            from prediccion p join modelo m on m.id = p.modelo_id and m.activo join obra o on o.cuaderno_id = p.cuaderno_id
            where p.fecha_corte = :corte and p.tipo = 'vigente' group by 1""", corte=corte)}
    for r in cart:
        x = cua.get(r["clave"]) if por == "departamento" else None
        r["cuaderno_evaluadas"] = x["evaluadas"] if x else 0
        r["cuaderno_alto"] = x["alto"] if x else 0
    out = {"por": por, "cartera": sorted(cart, key=lambda r: -(r["obras"] or 0))}
    if por == "sector":
        out["cuaderno_por_sector"] = list(cua.values())
    return out


@router.get("/ambitos")
@cacheado
def ambitos():
    return db.rows(
        """select departamento, count(*) obras from (
             select departamento from cartera_obra union all select departamento from obra) x
           where departamento is not null and departamento not like '%-%'
             and departamento not in ('NO APLICA', 'MULTIDEPARTAMENTAL') group by 1 order by 2 desc""")


@router.get("/ambitos/{departamento}/provincias")
@cacheado
def provincias(departamento: str = Path(..., max_length=40)):
    """Provincias con obras del departamento (la misma fuente con la que se validan las suscripciones)."""
    return [r["provincia"] for r in db.rows(
        """select provincia from (select provincia from obra where departamento = :d union select provincia from cartera_obra where departamento = :d) x
           where provincia is not null order by 1""", d=departamento.upper())]


@router.get("/filtros")
@cacheado
def filtros():
    """Valores disponibles para los filtros de la interfaz, leidos de los datos cargados (sin listas fijas)."""
    return {
        "sectores": [r["v"] for r in db.rows("select sector v, count(*) n from obra where sector is not null group by 1 order by 2 desc")],
        "tipos_obra": [r["v"] for r in db.rows("select tipo_obra v, count(*) n from cartera_obra where tipo_obra is not null group by 1 order by 2 desc")],
        "modalidades": [r["v"] for r in db.rows("select modalidad v, count(*) n from cartera_obra where modalidad is not null group by 1 order by 2 desc")],
    }
