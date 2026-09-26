import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, fmtFecha, fmtPct, qs, type Nivel } from '../api'
import { Cargando, ErrorMsg, NivelBadge, PROVINCIAS, SECTORES, Seccion } from '../components/ui'

interface Alerta {
  prediccion_id: number
  fecha_corte: string
  score: number
  percentil: number
  nivel: Nivel
  cuaderno_id: string
  denominacion: string
  provincia: string
  distrito: string
  sector: string
  entidad: string
  factores: { descripcion: string; shap: number; grupo: string }[] | null
  ultima_revision: { decision: string; creado_en: string } | null
}

export default function Alertas() {
  const [f, setF] = useState({ nivel: '', provincia: '', sector: '' })
  const q = useQuery({ queryKey: ['alertas', f], queryFn: () => api<{ fecha_corte: string; total: number; items: Alerta[] }>(`/alertas${qs({ ...f, limite: 300 })}`) })
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-marca-900">Alertas vigentes</h1>
        <p className="text-sm text-slate-500">
          Obras en ejecución con probabilidad elevada de registrar un <b>atraso significativo normativo</b> (valorización acumulada &lt; 80% de lo programado, RLCE art.
          203 / RLGCP art. 207) en los próximos 60 días. Corte: {fmtFecha(q.data?.fecha_corte)}.
        </p>
      </div>
      <div className="tarjeta flex flex-wrap items-end gap-3 p-3">
        <label className="text-sm">
          <div className="etiqueta mb-1">Nivel</div>
          <select className="entrada" value={f.nivel} onChange={(e) => setF({ ...f, nivel: e.target.value })}>
            <option value="">Alto y medio</option>
            <option value="ALTO">Alto</option>
            <option value="MEDIO">Medio</option>
          </select>
        </label>
        <label className="text-sm">
          <div className="etiqueta mb-1">Provincia</div>
          <select className="entrada" value={f.provincia} onChange={(e) => setF({ ...f, provincia: e.target.value })}>
            <option value="">Todas</option>
            {PROVINCIAS.map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <div className="etiqueta mb-1">Sector</div>
          <select className="entrada" value={f.sector} onChange={(e) => setF({ ...f, sector: e.target.value })}>
            <option value="">Todos</option>
            {SECTORES.map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </label>
        <span className="ml-auto text-sm text-slate-500">{q.data?.total ?? 0} alertas</span>
      </div>
      {q.isLoading ? (
        <Cargando />
      ) : q.error ? (
        <ErrorMsg error={q.error} />
      ) : (
        <Seccion titulo="Obras priorizadas" subtitulo="Ordenadas por probabilidad estimada. Los factores son las contribuciones TreeSHAP más altas hacia el riesgo, calculadas sobre datos reales.">
          <div className="overflow-x-auto">
            <table className="tabla w-full">
              <thead>
                <tr>
                  <th>Obra</th>
                  <th>Ubicación</th>
                  <th>Riesgo</th>
                  <th>Principales factores</th>
                  <th>Revisión</th>
                </tr>
              </thead>
              <tbody>
                {q.data!.items.map((a) => (
                  <tr key={a.prediccion_id}>
                    <td className="max-w-md">
                      <Link to={`/obras/${a.cuaderno_id}`} className="font-medium text-marca-700 hover:underline">
                        {a.denominacion.slice(0, 160)}
                        {a.denominacion.length > 160 ? '…' : ''}
                      </Link>
                      <div className="text-xs text-slate-500">{a.entidad}</div>
                    </td>
                    <td className="whitespace-nowrap text-xs">
                      {a.provincia}
                      <br />
                      {a.distrito}
                      <br />
                      <span className="text-slate-500">{a.sector}</span>
                    </td>
                    <td className="whitespace-nowrap">
                      <NivelBadge nivel={a.nivel} score={a.score} />
                      <div className="mt-1 text-xs text-slate-500">percentil {fmtPct(a.percentil)}</div>
                    </td>
                    <td className="text-xs">
                      <ul className="list-disc space-y-0.5 pl-4">
                        {(a.factores ?? []).map((x, i) => (
                          <li key={i}>{x.descripcion}</li>
                        ))}
                      </ul>
                    </td>
                    <td className="text-xs">{a.ultima_revision ? `${a.ultima_revision.decision} (${fmtFecha(a.ultima_revision.creado_en)})` : <span className="text-slate-400">pendiente</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Seccion>
      )}
    </div>
  )
}
