import { useQuery } from '@tanstack/react-query'
import { CircleMarker, MapContainer, TileLayer, Tooltip as MapTip } from 'react-leaflet'
import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, fmtFecha, fmtMes, fmtNum, type Nivel } from '../api'
import { Cargando, ErrorMsg, Kpi, NivelBadge, Seccion } from '../components/ui'

interface Resumen {
  fecha_corte: string
  kpi: { obras: number; en_ejecucion: number; con_atraso_normativo: number; con_cui: number; provincias: number; asientos: number }
  vigente: { evaluadas: number; alertas: number; alto: number; medio: number }
  por_provincia: { provincia: string; obras: number; en_ejecucion: number; con_atraso: number; alertas_vigentes: number }[]
  por_sector: { sector: string; obras: number; con_atraso: number; alertas_vigentes: number }[]
  historico: { fecha_corte: string; evaluadas: number; alertas: number; alertas_confirmadas: number; eventos_observados: number; observables: number }[]
}
interface PuntoMapa {
  cuaderno_id: string
  denominacion: string
  provincia: string
  sector: string
  latitud: number
  longitud: number
  score: number | null
  nivel: Nivel | null
  tipo_prediccion: string | null
}

const COLOR: Record<string, string> = { ALTO: '#b91c1c', MEDIO: '#d97706', BAJO: '#15803d' }

export default function Dashboard() {
  const r = useQuery({ queryKey: ['resumen'], queryFn: () => api<Resumen>('/estadisticas/resumen') })
  const m = useQuery({ queryKey: ['mapa'], queryFn: () => api<PuntoMapa[]>('/obras/mapa') })
  const a = useQuery({ queryKey: ['alertas-top'], queryFn: () => api<{ items: { prediccion_id: number; cuaderno_id: string; denominacion: string; provincia: string; nivel: Nivel; score: number; factores: { descripcion: string }[] | null }[] }>('/alertas?limite=8') })
  if (r.isLoading) return <Cargando />
  if (r.error) return <ErrorMsg error={r.error} />
  const d = r.data!
  const hist = d.historico.map((h) => ({ ...h, mes: fmtMes(h.fecha_corte) }))
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-xl font-bold text-marca-900">Panel de supervisión</h1>
          <p className="text-sm text-slate-500">
            Obras públicas con cuaderno de obra digital en las 8 provincias de Arequipa · corte de datos {fmtFecha(d.fecha_corte)}
          </p>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        <Kpi titulo="Obras registradas" valor={fmtNum(d.kpi.obras)} detalle={`${d.kpi.provincias} provincias`} />
        <Kpi titulo="En ejecución" valor={fmtNum(d.kpi.en_ejecucion)} detalle="con asientos en los últimos 90 días" />
        <Kpi titulo="Evaluadas hoy" valor={fmtNum(d.vigente.evaluadas)} detalle="elegibles para predicción" />
        <Kpi titulo="Alertas vigentes" valor={fmtNum(d.vigente.alertas)} tono="medio" detalle={`${d.vigente.alto} nivel alto · ${d.vigente.medio} medio`} />
        <Kpi titulo="Atraso normativo" valor={fmtNum(d.kpi.con_atraso_normativo)} tono="alto" detalle="obras con evento art. 203/207" />
        <Kpi titulo="Asientos analizados" valor={fmtNum(d.kpi.asientos)} detalle="cuaderno de obra digital (OECE)" />
      </div>

      <div className="grid gap-5 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <Seccion titulo="Mapa de obras por nivel de riesgo" subtitulo="Coordenadas referenciales registradas en el cuaderno de obra digital. Color = último nivel evaluado.">
            <div className="h-[430px] overflow-hidden rounded-lg">
              <MapContainer center={[-16.0, -72.4]} zoom={7} scrollWheelZoom className="h-full w-full">
                <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
                {(m.data ?? []).map((p) => (
                  <CircleMarker
                    key={p.cuaderno_id}
                    center={[p.latitud, p.longitud]}
                    radius={p.nivel === 'ALTO' ? 8 : p.nivel === 'MEDIO' ? 6.5 : 4.5}
                    pathOptions={{ color: p.nivel ? COLOR[p.nivel] : '#64748b', fillOpacity: 0.7, weight: 1 }}
                  >
                    <MapTip>
                      <div className="max-w-xs text-xs">
                        <b>{p.denominacion.slice(0, 120)}</b>
                        <br />
                        {p.provincia} · {p.sector} · {p.nivel ?? 'sin evaluación'} {p.score !== null ? `(${(100 * p.score).toFixed(0)}%)` : ''}
                      </div>
                    </MapTip>
                  </CircleMarker>
                ))}
              </MapContainer>
            </div>
          </Seccion>
        </div>
        <div className="lg:col-span-2">
          <Seccion titulo="Alertas de mayor riesgo" accion={<Link to="/alertas" className="text-sm text-marca-600 hover:underline">Ver todas</Link>}>
            {a.isLoading ? (
              <Cargando />
            ) : (a.data?.items.length ?? 0) === 0 ? (
              <p className="text-sm text-slate-500">No hay alertas vigentes.</p>
            ) : (
              <ul className="divide-y divide-slate-100">
                {a.data!.items.map((x) => (
                  <li key={x.prediccion_id} className="py-2">
                    <div className="flex items-start justify-between gap-2">
                      <Link to={`/obras/${x.cuaderno_id}`} className="text-sm font-medium text-marca-700 hover:underline">
                        {x.denominacion.slice(0, 110)}
                        {x.denominacion.length > 110 ? '…' : ''}
                      </Link>
                      <NivelBadge nivel={x.nivel} score={x.score} />
                    </div>
                    <div className="mt-0.5 text-xs text-slate-500">
                      {x.provincia} · {x.factores?.[0]?.descripcion ?? ''}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Seccion>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Seccion titulo="Obras y alertas por provincia">
          <div className="h-72">
            <ResponsiveContainer>
              <BarChart data={d.por_provincia} margin={{ left: -10 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="provincia" tick={{ fontSize: 11 }} interval={0} angle={-20} textAnchor="end" height={50} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="obras" name="Obras" fill="#1b5f8c" />
                <Bar dataKey="con_atraso" name="Con atraso normativo" fill="#b91c1c" />
                <Bar dataKey="alertas_vigentes" name="Alertas vigentes" fill="#d97706" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Seccion>
        <Seccion titulo="Validación histórica (backtest as-of)" subtitulo="Por cada corte mensual: alertas emitidas con información disponible a esa fecha y cuántas se confirmaron con un evento de atraso dentro del horizonte.">
          <div className="h-72">
            <ResponsiveContainer>
              <LineChart data={hist} margin={{ left: -10 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="mes" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line dataKey="alertas" name="Alertas emitidas" stroke="#d97706" dot={false} strokeWidth={2} />
                <Line dataKey="alertas_confirmadas" name="Alertas confirmadas" stroke="#15803d" dot={false} strokeWidth={2} />
                <Line dataKey="eventos_observados" name="Eventos de atraso observados" stroke="#b91c1c" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Seccion>
      </div>

      <Seccion titulo="Distribución por sector (función MEF de la inversión)">
        <div className="overflow-x-auto">
          <table className="tabla w-full">
            <thead>
              <tr>
                <th>Sector</th>
                <th className="text-right">Obras</th>
                <th className="text-right">Con atraso normativo</th>
                <th className="text-right">Alertas vigentes</th>
              </tr>
            </thead>
            <tbody>
              {d.por_sector.map((s) => (
                <tr key={s.sector}>
                  <td>{s.sector}</td>
                  <td className="text-right">{fmtNum(s.obras)}</td>
                  <td className="text-right">{fmtNum(s.con_atraso)}</td>
                  <td className="text-right">{fmtNum(s.alertas_vigentes)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Seccion>
    </div>
  )
}
