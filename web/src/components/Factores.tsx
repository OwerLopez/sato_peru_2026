import { useQuery } from '@tanstack/react-query'
import { ArrowDownRight, ArrowRight, ArrowUpRight, FileText } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, fmtDec, fmtFecha, fmtPct, useCalibracion, type Explicacion, type Factor, type Nivel } from '../api'
import { Cargando, ErrorMsg, EscalaRiesgo, InfoTip, NivelBadge } from './ui'
import { NIVEL_TEXTO } from '../lib/nivel'

// Lista de factores explicativos en lenguaje claro. Los valores técnicos (variable y contribución SHAP) quedan disponibles bajo demanda.
export function ListaFactores({ factores, tecnico: tecnicoInicial = false, alVerEvidencia, conEvidencia }: { factores: Factor[]; tecnico?: boolean; alVerEvidencia?: (f: Factor) => void; conEvidencia?: Set<string> }) {
  const [tecnico, setTecnico] = useState(tecnicoInicial)
  const max = Math.max(...factores.map((f) => Math.abs(f.shap)), 0.001)
  return (
    <div>
      <ul className="divide-y divide-slate-100">
        {factores.map((f, i) => {
          const sube = f.shap > 0
          return (
            <li key={f.feature ?? i} className="flex gap-3 py-2.5">
              <span className={`mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full ${sube ? 'bg-alto-suave text-alto' : 'bg-bajo-suave text-bajo'}`} aria-hidden>
                {sube ? <ArrowUpRight className="size-3.5" /> : <ArrowDownRight className="size-3.5" />}
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-sm leading-snug text-slate-800">{f.descripcion}</div>
                <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
                  <span>{sube ? 'Eleva el riesgo' : 'Reduce el riesgo'}</span>
                  <span className="flex w-20 items-center" aria-hidden>
                    <span className={`h-1 rounded-full ${sube ? 'bg-alto/70' : 'bg-bajo/70'}`} style={{ width: `${Math.max(8, (100 * Math.abs(f.shap)) / max)}%` }} />
                  </span>
                  <span>{f.grupo}</span>
                  {alVerEvidencia && f.feature && conEvidencia?.has(f.feature) && (
                    <button className="enlace text-xs" onClick={() => alVerEvidencia(f)}>
                      Ver evidencia
                    </button>
                  )}
                </div>
                {tecnico && (
                  <div className="mt-1 font-mono text-[11px] text-slate-500">
                    {f.feature} = {f.valor === null || f.valor === undefined ? 'categoría' : fmtDec(f.valor, 3)} · SHAP {f.shap > 0 ? '+' : ''}
                    {fmtDec(f.shap, 3)} (log-odds)
                  </div>
                )}
              </div>
            </li>
          )
        })}
      </ul>
      <label className="mt-2 inline-flex items-center gap-2 text-xs text-slate-500">
        <input type="checkbox" checked={tecnico} onChange={(e) => setTecnico(e.target.checked)} className="accent-marca-600" />
        Mostrar detalle técnico (variable y contribución TreeSHAP)
      </label>
    </div>
  )
}

// Frase de confiabilidad del nivel, con la tasa realmente observada en el backtest.
export function ConfianzaNivel({ nivel }: { nivel: Nivel }) {
  const c = useCalibracion()
  const n = c.data?.alerta_60d.niveles.find((x) => x.nivel === nivel)
  if (!n || !c.data) return null
  return (
    <p className="text-sm leading-relaxed text-slate-600">
      En la validación con datos pasados, <b className="num text-slate-900">{Math.round(100 * n.tasa_observada)} de cada 100</b> obras en nivel {NIVEL_TEXTO[nivel].toLowerCase()} registraron el atraso formal dentro de 60 días. En promedio ocurre en{' '}
      <span className="num">{Math.round(100 * c.data.alerta_60d.tasa_base)}</span> de cada 100.
      <InfoTip termino="confiabilidad" className="ml-1 align-[-2px]" />
    </p>
  )
}

export function VecesPromedio({ score, base }: { score: number; base: number | undefined }) {
  if (!base) return null
  const v = score / base
  return (
    <span className="inline-flex items-center gap-1 text-sm text-slate-600">
      <span className="num font-semibold text-slate-900">{v >= 10 ? Math.round(v) : fmtDec(v, 1)} veces</span> el promedio
      <InfoTip termino="veces_promedio" />
    </span>
  )
}

// Vista previa de una predicción del cuaderno (para paneles laterales).
export function VistaPreviaCuaderno({ prediccionId, cuadernoId, nombre }: { prediccionId: number; cuadernoId: string; nombre: string }) {
  const q = useQuery({ queryKey: ['exp', prediccionId], queryFn: () => api<Explicacion>(`/predicciones/${prediccionId}`) })
  const cal = useCalibracion()
  if (q.isLoading) return <Cargando filas={6} />
  if (q.error) return <ErrorMsg error={q.error} reintentar={() => q.refetch()} />
  const p = q.data!.prediccion
  const suben = q.data!.factores.filter((f) => f.shap > 0)
  return (
    <div className="space-y-5">
      <div className="text-sm font-medium text-slate-900">{nombre}</div>
      <div className="grid grid-cols-2 gap-4 rounded-xl border border-slate-200 p-4">
        <div>
          <div className="text-xs text-slate-500">Riesgo de atraso formal en {p.horizonte_dias} días</div>
          <div className="mt-1">
            <NivelBadge nivel={p.nivel} />
          </div>
          <div className="num mt-2 text-2xl font-semibold text-slate-900">{fmtPct(p.score)}</div>
          <VecesPromedio score={p.score} base={cal.data?.alerta_60d.tasa_base} />
        </div>
        <EscalaRiesgo percentil={p.percentil} nivel={p.nivel} />
      </div>
      <ConfianzaNivel nivel={p.nivel} />
      <div>
        <div className="etiqueta mb-1">Qué eleva el riesgo</div>
        {suben.length ? <ListaFactores factores={suben.slice(0, 5)} /> : <p className="text-sm text-slate-500">Ningún factor eleva el riesgo por encima del promedio.</p>}
      </div>
      <div className="flex flex-wrap gap-2 border-t border-slate-100 pt-4">
        <Link to={`/obras/${cuadernoId}`} className="btn-primario">
          Ver ficha completa <ArrowRight className="size-4" />
        </Link>
        <a href={`/api/v1/obras/${cuadernoId}/informe-pdf`} className="btn">
          <FileText className="size-4" /> Informe PDF
        </a>
      </div>
      <p className="text-xs text-slate-500">Corte {fmtFecha(p.fecha_corte)} · modelo {p.modelo_version}</p>
    </div>
  )
}
