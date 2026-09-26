from __future__ import annotations

import datetime as dt
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from sato.api import db
from sato.api.security import audit, current_user, require_role

router = APIRouter(tags=["alertas"])


@router.get("/alertas")
def alertas(
    fecha_corte: dt.date | None = None,
    nivel: Literal["ALTO", "MEDIO"] | None = None,
    provincia: str | None = None,
    sector: str | None = None,
    incluir_vigilancia: bool = False,
    limite: int = Query(100, ge=1, le=500),
):
    """Alertas (nivel ALTO) del corte indicado -por defecto el vigente- con sus 3 principales factores de riesgo.

    Con `incluir_vigilancia=true` tambien se devuelven las obras de nivel MEDIO ("en vigilancia")."""
    corte = fecha_corte or (db.one("select max(fecha_corte) f from prediccion where tipo = 'vigente'") or {}).get("f")
    items = db.rows(
        """select p.id prediccion_id, p.fecha_corte, p.tipo, p.score, p.nivel, p.percentil, p.y_observado,
                  o.cuaderno_id, o.denominacion, o.provincia, o.distrito, o.sector, o.cui, o.estado_observado, e.nombre entidad,
                  (select json_agg(json_build_object('descripcion', x.descripcion, 'shap', x.shap, 'grupo', x.grupo) order by x.shap desc)
                     from (select * from explicacion where prediccion_id = p.id and shap > 0 order by shap desc limit 3) x) factores,
                  (select json_build_object('decision', r.decision, 'creado_en', r.creado_en) from revision_alerta r
                    where r.cuaderno_id = o.cuaderno_id and r.fecha_corte = p.fecha_corte order by r.creado_en desc limit 1) ultima_revision
           from prediccion p join modelo m on m.id = p.modelo_id and m.activo
           join obra o on o.cuaderno_id = p.cuaderno_id left join entidad e on e.ruc = o.entidad_ruc
           where p.fecha_corte = :corte and (p.alerta or (:vig and p.nivel = 'MEDIO')) and (cast(:nivel as text) is null or p.nivel = :nivel)
             and (cast(:prov as text) is null or o.provincia = :prov) and (cast(:sector as text) is null or o.sector = :sector)
           order by p.score desc limit :lim""",
        corte=corte, nivel=nivel, prov=provincia, sector=sector, vig=incluir_vigilancia or nivel == "MEDIO", lim=limite,
    )
    return {"fecha_corte": corte, "total": len(items), "items": items}


@router.get("/predicciones/{prediccion_id}")
def explicacion(prediccion_id: int):
    """Por que el sistema genero esta prediccion y que registros reales la respaldan."""
    p = db.one(
        """select p.*, m.version modelo_version, m.horizonte_dias, m.umbral_alerta, m.objetivo, o.denominacion
           from prediccion p join modelo m on m.id = p.modelo_id join obra o on o.cuaderno_id = p.cuaderno_id where p.id = :id""",
        id=prediccion_id,
    )
    if not p:
        raise HTTPException(404, "Prediccion no encontrada")
    factores = db.rows("select rango, feature, grupo, valor, shap, descripcion from explicacion where prediccion_id = :id order by rango", id=prediccion_id)
    evid = db.rows(
        """select ev.feature, ev.fuente, ev.fecha, ev.referencia, ev.extracto, ev.asiento_id,
                  a.nro_asiento, a.tipo, a.rol, a.titulo, a.archivo_fuente
           from evidencia ev left join asiento a on a.id = ev.asiento_id where ev.prediccion_id = :id order by ev.feature, ev.fecha desc""",
        id=prediccion_id,
    )
    return {"prediccion": p, "factores": factores, "evidencia": evid}


class RevisionIn(BaseModel):
    decision: Literal["CONFIRMADA", "DESCARTADA", "EN_SEGUIMIENTO"]
    comentario: str | None = Field(None, max_length=2000)


@router.get("/alertas/{cuaderno_id}/{fecha_corte}/revisiones")
def revisiones(cuaderno_id: UUID, fecha_corte: dt.date, _u: dict = Depends(current_user)):
    return db.rows(
        """select r.id, r.decision, r.comentario, r.creado_en, r.modelo_version, u.nombre usuario from revision_alerta r
           join usuario u on u.id = r.usuario_id where r.cuaderno_id = :c and r.fecha_corte = :f order by r.creado_en desc""",
        c=str(cuaderno_id), f=fecha_corte,
    )


@router.post("/alertas/{cuaderno_id}/{fecha_corte}/revisiones", status_code=201)
def revisar(cuaderno_id: UUID, fecha_corte: dt.date, body: RevisionIn, request: Request, u: dict = Depends(require_role("analista", "admin"))):
    m = db.one("select version from modelo where activo")
    if not db.one("select 1 x from prediccion where cuaderno_id = :c and fecha_corte = :f", c=str(cuaderno_id), f=fecha_corte):
        raise HTTPException(404, "No existe prediccion para esa obra y corte")
    r = db.execute(
        """insert into revision_alerta (cuaderno_id, fecha_corte, modelo_version, usuario_id, decision, comentario)
           values (:c, :f, :v, :u, :d, :t) returning id, creado_en""",
        c=str(cuaderno_id), f=fecha_corte, v=m["version"] if m else "desconocida", u=u["id"], d=body.decision, t=body.comentario,
    )
    audit(request, "REVISION_ALERTA", u["id"], f"obra:{cuaderno_id}:{fecha_corte}", body.model_dump())
    return r
