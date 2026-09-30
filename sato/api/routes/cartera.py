from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from sato.api import db
from sato.api.cache import cacheado

router = APIRouter(prefix="/cartera", tags=["cartera"])

# riesgo vigente de cada obra de la cartera (vista materializada que se refresca en cada carga)
LAST = " left join cartera_riesgo_vigente lr on lr.codigo_infobras = c.codigo_infobras "


@router.get("")
def listar(departamento: str | None = None, provincia: str | None = None, tipo_obra: str | None = None, modalidad: str | None = None,
           estado: Literal["ACTIVA", "CONSUMADO", "FINALIZADA", "DESACTUALIZADA"] | None = None, nivel: Literal["ALTO", "MEDIO", "BAJO"] | None = None,
           q: str | None = Query(None, max_length=120), orden: Literal["riesgo", "monto", "reciente"] = "riesgo",
           pagina: int = Query(1, ge=1), tamanio: int = Query(25, ge=1, le=100)):
    where = """where (cast(:dep as text) is null or c.departamento = :dep) and (cast(:prov as text) is null or c.provincia = :prov)
      and (cast(:tipo as text) is null or c.tipo_obra = :tipo) and (cast(:mod as text) is null or c.modalidad = :mod)
      and (cast(:est as text) is null or c.estado_operativo = :est) and (cast(:nivel as text) is null or lr.nivel = :nivel)
      and (cast(:q as text) is null or c.nombre ilike :qq escape '!' or c.cui = :q or c.codigo_infobras = :q or c.entidad ilike :qq escape '!')"""
    q = q.strip() if q and q.strip() else None
    p = dict(dep=departamento, prov=provincia, tipo=tipo_obra, mod=modalidad, est=estado, nivel=nivel, q=q, qq=db.patron(q))
    order = {"riesgo": "lr.score desc nulls last", "monto": "c.costo desc nulls last", "reciente": "c.fecha_inicio desc nulls last"}[orden]
    total = db.one(f"select count(*) n from cartera_obra c {LAST} {where}", **p)["n"]
    items = db.rows(f"""select c.codigo_infobras, c.nombre, c.departamento, c.provincia, c.distrito, c.tipo_obra, c.modalidad, c.costo,
                               c.estado_operativo, c.fecha_inicio, c.fin_programado, c.fin_real, c.sobreplazo, c.retraso_significativo, c.entidad,
                               c.cuaderno_id, lr.modelo, lr.fecha_corte, lr.score, lr.nivel
                        from cartera_obra c {LAST} {where} order by {order} limit :lim offset :off""",
                    **p, lim=tamanio, off=(pagina - 1) * tamanio)
    return {"total": total, "pagina": pagina, "items": items}


@router.get("/mapa")
@cacheado
def mapa(departamento: str | None = None, estado: Literal["ACTIVA", "CONSUMADO"] = "ACTIVA"):
    return db.rows(f"""select c.codigo_infobras, c.nombre, c.departamento, c.provincia, c.tipo_obra, c.costo, c.latitud, c.longitud,
                              lr.score, lr.nivel, lr.modelo
                       from cartera_obra c {LAST}
                       where c.estado_operativo = :est and c.latitud is not null and (cast(:dep as text) is null or c.departamento = :dep)""",
                   est=estado, dep=departamento)


@router.get("/{codigo}")
def detalle(codigo: str):
    if len(codigo) > 20:
        raise HTTPException(422, "codigo invalido")
    c = db.one("select * from cartera_obra where codigo_infobras = :c", c=codigo)
    if not c:
        raise HTTPException(404, "Obra no encontrada")
    riesgos = db.rows("select id riesgo_id, tipo, fecha_corte, score, nivel, y_observado, modelo_origen from cartera_riesgo where codigo_infobras = :c order by tipo, fecha_corte", c=codigo)
    expl = {}
    for tipo in ("inicio", "seguimiento"):
        last = [r for r in riesgos if r["tipo"] == tipo]
        if last:
            expl[tipo] = db.rows("select rango, feature, grupo, valor, shap, descripcion from cartera_explicacion where riesgo_id = :r order by rango",
                                 r=last[-1]["riesgo_id"])
    siaf = db.rows("select make_date(anio, mes, 1) mes, devengado from siaf_mensual where cui = :cui and anio >= 2017 order by 1", cui=c["cui"]) if c["cui"] else []
    ib = db.one("select * from infobras_obra where codigo_infobras = :c", c=codigo)
    par = db.rows("select fecha_corte, avance_fisico, causal from contraloria_paralizada where codigo_infobras = :c or (cui = :cui and :cui is not null) order by fecha_corte",
                  c=codigo, cui=c["cui"])
    card = (db.one("select valor from configuracion where clave = 'modelo_cartera'") or {}).get("valor")
    enlaces = [{"fuente": "INFOBRAS - Contraloria", "url": f"https://infobras.contraloria.gob.pe/InfobrasWeb/Mapa/Sumario?ObraId={codigo}"}]
    if c["cui"]:
        enlaces.append({"fuente": "MEF - Seguimiento de inversiones (SSI)", "url": f"https://ofi5.mef.gob.pe/ssi/Ssi/Index?codigo={c['cui']}&tipo=2"})
    return {"obra": c, "riesgos": riesgos, "explicaciones": expl, "siaf_mensual": siaf, "infobras": ib, "contraloria_paralizada": par,
            "enlaces": enlaces, "umbrales": card.get("umbrales") if card else None}
