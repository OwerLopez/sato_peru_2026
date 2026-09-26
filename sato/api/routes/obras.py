from __future__ import annotations

import datetime as dt
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from sato.api import db

router = APIRouter(prefix="/obras", tags=["obras"])

LATEST = """
  left join lateral (
    select p.id prediccion_id, p.fecha_corte, p.score, p.nivel, p.alerta, p.percentil, p.tipo
    from prediccion p join modelo m on m.id = p.modelo_id and m.activo
    where p.cuaderno_id = o.cuaderno_id order by p.fecha_corte desc limit 1
  ) lp on true
"""


@router.get("")
def listar(
    provincia: str | None = None,
    sector: str | None = None,
    estado: Literal["EN_EJECUCION", "CULMINADA", "RESUELTA", "INACTIVA"] | None = None,
    nivel: Literal["ALTO", "MEDIO", "BAJO"] | None = None,
    solo_vigentes: bool = False,
    q: str | None = Query(None, max_length=120),
    orden: Literal["riesgo", "reciente", "nombre"] = "riesgo",
    pagina: int = Query(1, ge=1),
    tamanio: int = Query(25, ge=1, le=100),
):
    order = {"riesgo": "lp.score desc nulls last", "reciente": "o.ultimo_asiento desc nulls last", "nombre": "o.denominacion"}[orden]
    where = """where (cast(:prov as text) is null or o.provincia = :prov)
      and (cast(:sector as text) is null or o.sector = :sector)
      and (cast(:estado as text) is null or o.estado_observado = :estado)
      and (cast(:nivel as text) is null or lp.nivel = :nivel)
      and (not :solo or lp.tipo = 'vigente')
      and (cast(:q as text) is null or o.denominacion ilike '%' || :q || '%' or o.cui = :q or e.nombre ilike '%' || :q || '%')"""
    p = dict(prov=provincia, sector=sector, estado=estado, nivel=nivel, solo=solo_vigentes, q=q)
    total = db.one(f"select count(*) n from obra o left join entidad e on e.ruc = o.entidad_ruc {LATEST} {where}", **p)["n"]
    items = db.rows(
        f"""select o.cuaderno_id, o.denominacion, o.provincia, o.distrito, o.sector, o.cui, o.estado_observado,
                   o.latitud, o.longitud, o.primer_asiento, o.ultimo_asiento, o.n_asientos, o.fecha_atraso,
                   e.nombre entidad, lp.prediccion_id, lp.fecha_corte, lp.score, lp.nivel, lp.alerta, lp.percentil, lp.tipo tipo_prediccion
            from obra o left join entidad e on e.ruc = o.entidad_ruc {LATEST} {where}
            order by {order} limit :lim offset :off""",
        **p, lim=tamanio, off=(pagina - 1) * tamanio,
    )
    return {"total": total, "pagina": pagina, "tamanio": tamanio, "items": items}


@router.get("/mapa")
def mapa():
    """Obras con coordenadas y su ultimo nivel de riesgo (para el mapa)."""
    return db.rows(
        f"""select o.cuaderno_id, o.denominacion, o.provincia, o.sector, o.estado_observado, o.latitud, o.longitud,
                   lp.score, lp.nivel, lp.alerta, lp.tipo tipo_prediccion
            from obra o {LATEST}
            where o.latitud between -18.5 and -14 and o.longitud between -76 and -70"""
    )


@router.get("/{cuaderno_id}")
def detalle(cuaderno_id: UUID):
    o = db.one(
        f"""select o.*, e.nombre entidad, e.ruc entidad_ruc, c.nombre contratista,
                   i.nombre inversion_nombre, i.funcion, i.nivel_gobierno, i.tipo_inversion, i.monto_viable, i.estado estado_inversion,
                   lp.prediccion_id, lp.fecha_corte, lp.score, lp.nivel, lp.alerta, lp.percentil, lp.tipo tipo_prediccion
            from obra o left join entidad e on e.ruc = o.entidad_ruc left join contratista c on c.ruc = o.contratista_ruc
            left join inversion i on i.cui = o.cui {LATEST}
            where o.cuaderno_id = :id""",
        id=str(cuaderno_id),
    )
    if not o:
        raise HTTPException(404, "Obra no encontrada")
    ib = db.one("select * from infobras_obra where codigo_infobras = :c", c=o["codigo_infobras"]) if o.get("codigo_infobras") else None
    par = db.rows("select fecha_corte, avance_fisico, causal from contraloria_paralizada where cui = :cui or codigo_infobras = :ib order by fecha_corte",
                  cui=o.get("cui"), ib=o.get("codigo_infobras"))
    enlaces = []
    if o.get("cui"):
        enlaces.append({"fuente": "MEF - Seguimiento de inversiones (SSI)", "url": f"https://ofi5.mef.gob.pe/ssi/Ssi/Index?codigo={o['cui']}&tipo=2"})
    if o.get("codigo_infobras"):
        enlaces.append({"fuente": "INFOBRAS - Contraloria", "url": f"https://infobras.contraloria.gob.pe/InfobrasWeb/Mapa/Sumario?ObraId={o['codigo_infobras']}"})
    if o.get("url_contrato_seace"):
        enlaces.append({"fuente": "SEACE - Contrato", "url": o["url_contrato_seace"]})
    return {"obra": o, "infobras": ib, "contraloria_paralizada": par, "enlaces": enlaces}


@router.get("/{cuaderno_id}/riesgo")
def riesgo(cuaderno_id: UUID):
    """Evolucion temporal: predicciones (backtest as-of y vigente), actividad del cuaderno y ejecucion SIAF."""
    oid = str(cuaderno_id)
    if not db.one("select 1 x from obra where cuaderno_id = :id", id=oid):
        raise HTTPException(404, "Obra no encontrada")
    preds = db.rows(
        """select p.id prediccion_id, p.fecha_corte, p.tipo, p.score, p.nivel, p.alerta, p.y_observado
           from prediccion p join modelo m on m.id = p.modelo_id and m.activo where p.cuaderno_id = :id order by p.fecha_corte""",
        id=oid,
    )
    actividad = db.rows(
        """select date_trunc('month', fecha)::date mes, count(*) total,
                  count(*) filter (where tipo_std = 'AMPLIACION_PLAZO') ampliaciones,
                  count(*) filter (where tipo_std = 'SUSPENSION_PLAZO') suspensiones,
                  count(*) filter (where tipo_std = 'ADICIONALES') adicionales,
                  count(*) filter (where tipo_std in ('VALORIZACION_MENOR_80','CALENDARIO_ACELERADO')) atraso_normativo
           from asiento where cuaderno_id = :id group by 1 order by 1""",
        id=oid,
    )
    siaf = db.rows(
        """select make_date(s.anio, s.mes, 1) mes, s.devengado from siaf_mensual s join obra o on o.cui = s.cui
           where o.cuaderno_id = :id and s.anio >= 2023 order by 1""",
        id=oid,
    )
    eventos = db.rows(
        """select fecha, tipo, tipo_std, nro_asiento, titulo from asiento where cuaderno_id = :id and tipo_std in
           ('APERTURA','INICIO_PLAZO','VALORIZACION_MENOR_80','CALENDARIO_ACELERADO','SUSPENSION_PLAZO','RESOLUCION_CONTRATO',
            'CULMINACION','RECEPCION','CIERRE') order by fecha, nro_asiento""",
        id=oid,
    )
    return {"predicciones": preds, "actividad_mensual": actividad, "siaf_mensual": siaf, "eventos": eventos}


@router.get("/{cuaderno_id}/asientos")
def asientos(
    cuaderno_id: UUID,
    tipo: str | None = Query(None, max_length=40),
    q: str | None = Query(None, max_length=200),
    desde: dt.date | None = None,
    hasta: dt.date | None = None,
    pagina: int = Query(1, ge=1),
    tamanio: int = Query(20, ge=1, le=100),
):
    p = dict(id=str(cuaderno_id), tipo=tipo, q=q, desde=desde, hasta=hasta)
    where = """where cuaderno_id = :id and (cast(:tipo as text) is null or tipo_std = :tipo)
      and (cast(:desde as date) is null or fecha >= :desde) and (cast(:hasta as date) is null or fecha <= :hasta)
      and (cast(:q as text) is null or tsv @@ websearch_to_tsquery('sato.es_unaccent', :q))"""
    total = db.one(f"select count(*) n from asiento {where}", **p)["n"]
    items = db.rows(
        f"""select id, nro_asiento, fecha, fecha_hora, rol, tipo, tipo_std, titulo, descripcion, archivo_fuente from asiento {where}
            order by fecha desc, nro_asiento desc limit :lim offset :off""",
        **p, lim=tamanio, off=(pagina - 1) * tamanio,
    )
    return {"total": total, "pagina": pagina, "items": items}
