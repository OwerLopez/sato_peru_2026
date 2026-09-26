import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { CircleMarker, MapContainer, TileLayer, Tooltip as MapTip, useMap } from 'react-leaflet'
import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, fmtFecha, fmtMes, fmtMillones, fmtNum, mensajeCartera, mensajeCuaderno, qs, type Nivel } from '../api'
import { useAmbito } from '../ambito'
import { Cargando, ErrorMsg, NivelBadge, Seccion } from '../components/ui'

interface Resumen {
  fecha_corte_cuaderno: string
  cuaderno: { activas: number; alto: number; medio: number; monto_activo: number; monto_alto: number }
  cartera: { activas: number; alto: number; medio: number; monto_activo: number; monto_alto: number; con_cuaderno: number }
  consolidado: { obras: number; en_ambos: number; monto: number; alto: number; monto_alto: number }
  cartera_otros: { consumado: number; desactualizada: number; finalizadas: number; tasa_historica: number }
  distribucion: { ambito: string; evaluadas: number; alto: number }[]
  historico: { fecha_corte: string; evaluadas: number; alertas: number; alertas_confirmadas: number; eventos_observados: number }[]
}
interface ItemC {
  prediccion_id: number
  cuaderno_id: string
  nombre: string
  departamento: string
  provincia: string
  sector: string
  monto: number | null
  score: number
  nivel: Nivel
  entidad: string
  factores: { descripcion: string }[] | null
}
interface ItemK {
  codigo_infobras: string
  nombre: string
  departamento: string
  provincia: string
  tipo_obra: string
  modalidad: string
  monto: number | null
  modelo: string
  score: number
  nivel: Nivel
  entidad: string
  fin_programado: string
  factores: { descripcion: string }[] | null
}
interface Punto {
  id: string
  nombre: string
  lat: number
  lon: number
  nivel: Nivel | null
  score: number | null
  tipo: 'cuaderno' | 'cartera'
}

const COLOR: Record<string, string> = { ALTO: '#b91c1c', MEDIO: '#d97706', BAJO: '#15803d' }

function Encuadre({ puntos, clave }: { puntos: Punto[]; clave: string }) {
  const map = useMap()
  useEffect(() => {
    if (!puntos.length) return
    const lats = puntos.map((p) => p.lat).sort((a, b) => a - b)
    const lons = puntos.map((p) => p.lon).sort((a, b) => a - b)
    const q = (a: number[], f: number) => a[Math.min(a.length - 1, Math.max(0, Math.floor(f * (a.length - 1))))]
    map.fitBounds([
      [q(lats, 0.01), q(lons, 0.01)],
      [q(lats, 0.99), q(lons, 0.99)],
    ], { padding: [20, 20], maxZoom: 9 })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clave])
  return null
}

function Hero({ titulo, valor, detalle, tono }: { titulo: string; valor: string; detalle: string; tono?: 'alto' | 'normal' }) {
  return (
    <div className={`rounded-xl p-4 shadow-sm ${tono === 'alto' ? 'bg-red-700 text-white' : 'bg-marca-800 text-white'}`}>
      <div className="text-xs font-medium uppercase tracking-wide opacity-95">{titulo}</div>
      <div className="mt-1 text-3xl font-bold">{valor}</div>
      <div className="mt-1 text-xs opacity-95">{detalle}</div>
    </div>
  )
}

export default function Radar() {
  const { departamento } = useAmbito()
  const [tab, setTab] = useState<'cuaderno' | 'cartera'>('cuaderno')
  const [nivel, setNivel] = useState<'' | Nivel>('ALTO')
  const p = { departamento }
  const r = useQuery({ queryKey: ['resumen', departamento], queryFn: () => api<Resumen>(`/resumen${qs(p)}`) })
  const rc = useQuery({ queryKey: ['radar-c', departamento, nivel], queryFn: () => api<{ items: ItemC[] }>(`/radar/cuaderno${qs({ ...p, nivel, limite: 300 })}`) })
  const rk = useQuery({ queryKey: ['radar-k', departamento, nivel], queryFn: () => api<{ items: ItemK[] }>(`/radar/cartera${qs({ ...p, nivel, limite: 300 })}`) })
  const mc = useQuery({
    queryKey: ['mapa-c', departamento],
    queryFn: () => api<{ cuaderno_id: string; denominacion: string; latitud: number; longitud: number; nivel: Nivel; score: number }[]>(`/obras/mapa${qs(p)}`),
  })
  const mk = useQuery({
    queryKey: ['mapa-k', departamento],
    queryFn: () => api<{ codigo_infobras: string; nombre: string; latitud: number; longitud: number; nivel: Nivel; score: number }[]>(`/cartera/mapa${qs(p)}`),
  })
  if (r.isLoading) return <Cargando texto="Cargando el radar de obras activas…" />
  if (r.error) return <ErrorMsg error={r.error} />
  const d = r.data!
  const puntos: Punto[] = [
    ...(mc.data ?? []).map((x) => ({ id: x.cuaderno_id, nombre: x.denominacion, lat: x.latitud, lon: x.longitud, nivel: x.nivel, score: x.score, tipo: 'cuaderno' as const })),
    ...(mk.data ?? []).map((x) => ({ id: x.codigo_infobras, nombre: x.nombre, lat: x.latitud, lon: x.longitud, nivel: x.nivel, score: x.score, tipo: 'cartera' as const })),
  ]
  const ambito = departamento ?? 'todo el Perú'
  const hist = d.historico.map((h) => ({ ...h, mes: fmtMes(h.fecha_corte) }))
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold text-marca-900">Radar de obras públicas activas</h1>
          <p className="text-sm text-slate-600">
            Predicción a futuro sobre obras en ejecución en {ambito}. Cuaderno de obra digital: corte {fmtFecha(d.fecha_corte_cuaderno)}; cartera INFOBRAS: registros
            hasta 31/03/2026. Las obras terminadas o con atraso ya consumado están en el{' '}
            <Link to="/laboratorio" className="text-marca-600 underline">
              Laboratorio de validación histórica
            </Link>
            .
          </p>
        </div>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Hero
          titulo="Obras activas monitoreadas"
          valor={fmtNum(d.consolidado.obras)}
          detalle={`${fmtNum(d.cuaderno.activas)} con cuaderno digital · ${fmtNum(d.cartera.activas)} de la cartera INFOBRAS · ${fmtNum(d.consolidado.en_ambos)} evaluadas por ambos modelos (contadas una vez)`}
        />
        <Hero
          titulo="Inversión bajo vigilancia"
          valor={fmtMillones(d.consolidado.monto ?? 0)}
          detalle="monto de contrato (cuaderno) o costo (INFOBRAS) de las obras activas evaluadas, sin doble conteo"
        />
        <Hero titulo="Alerta crítica a 60 días" valor={fmtNum(d.cuaderno.alto)} tono="alto" detalle={`obras con cuaderno digital en nivel alto · ${fmtNum(d.cuaderno.medio)} en vigilancia`} />
        <Hero
          titulo="Presupuesto de obras en alerta alta"
          valor={fmtMillones(d.consolidado.monto_alto ?? 0)}
          tono="alto"
          detalle={`${fmtNum(d.consolidado.alto)} obras en nivel alto en al menos un modelo; es el presupuesto comprometido, no una pérdida estimada`}
        />
      </div>

      <div className="grid gap-5 xl:grid-cols-5">
        <div className="xl:col-span-3">
          <Seccion titulo="Mapa de riesgo de obras activas" subtitulo="Color: nivel de riesgo vigente. Coordenadas referenciales (cuaderno digital) o de la inversión (Banco de Inversiones).">
            <div className="h-[460px] overflow-hidden rounded-lg">
              <MapContainer center={[-9.2, -75.0]} zoom={5} scrollWheelZoom={false} preferCanvas className="h-full w-full">
                <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
                <Encuadre puntos={puntos} clave={`${departamento ?? 'PE'}-${puntos.length}`} />
                {puntos.map((x) => (
                  <CircleMarker
                    key={x.tipo + x.id}
                    center={[x.lat, x.lon]}
                    radius={x.nivel === 'ALTO' ? 6 : x.nivel === 'MEDIO' ? 4.5 : 3}
                    pathOptions={{ color: x.nivel ? COLOR[x.nivel] : '#64748b', fillOpacity: 0.6, weight: x.tipo === 'cuaderno' ? 1.5 : 0.5 }}
                  >
                    <MapTip>
                      <div className="max-w-xs text-xs">
                        <b>{x.nombre.slice(0, 110)}</b>
                        <br />
                        {x.tipo === 'cuaderno' ? 'Cuaderno digital (60 días)' : 'Cartera INFOBRAS (al término)'} · {x.nivel} {x.score !== null ? `${(100 * x.score).toFixed(0)}%` : ''}
                      </div>
                    </MapTip>
                  </CircleMarker>
                ))}
              </MapContainer>
            </div>
          </Seccion>
        </div>
        <div className="xl:col-span-2">
          <Seccion
            titulo={departamento ? 'Obras con cuaderno digital por provincia' : 'Obras con cuaderno digital por departamento'}
            subtitulo="Evaluadas en el corte vigente y cuántas están en nivel alto."
          >
            <div className="h-[430px]">
              <ResponsiveContainer>
                <BarChart data={d.distribucion.slice(0, 25)} layout="vertical" margin={{ left: 40 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 11 }} />
                  <YAxis dataKey="ambito" type="category" tick={{ fontSize: 9 }} width={95} interval={0} />
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar isAnimationActive={false} dataKey="evaluadas" name="Evaluadas" fill="#1b5f8c" />
                  <Bar isAnimationActive={false} dataKey="alto" name="Nivel alto" fill="#b91c1c" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Seccion>
        </div>
      </div>

      <section className="tarjeta">
        <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 px-4 py-3">
          <button className={tab === 'cuaderno' ? 'btn-primario' : 'btn'} onClick={() => setTab('cuaderno')}>
            Alerta a 60 días · cuaderno de obra digital ({fmtNum(rc.data?.items.length)})
          </button>
          <button className={tab === 'cartera' ? 'btn-primario' : 'btn'} onClick={() => setTab('cartera')}>
            Riesgo al término · cartera INFOBRAS ({fmtNum(rk.data?.items.length)})
          </button>
          <label className="ml-auto flex items-center gap-2 text-sm">
            <span className="etiqueta">Nivel</span>
            <select className="entrada" value={nivel} onChange={(e) => setNivel(e.target.value as Nivel | '')}>
              <option value="ALTO">Alto</option>
              <option value="MEDIO">Medio</option>
              <option value="BAJO">Bajo</option>
              <option value="">Todos</option>
            </select>
          </label>
        </div>
        <div className="p-4">
          {tab === 'cuaderno' ? (
            rc.isLoading ? (
              <Cargando />
            ) : (
              <ul className="divide-y divide-slate-100">
                {(rc.data?.items ?? []).map((x) => (
                  <li key={x.prediccion_id} className="grid gap-2 py-3 md:grid-cols-[1fr_auto]">
                    <div>
                      <Link to={`/obras/${x.cuaderno_id}`} className="font-medium text-marca-700 hover:underline">
                        {x.nombre.slice(0, 180)}
                        {x.nombre.length > 180 ? '…' : ''}
                      </Link>
                      <div className="text-xs text-slate-500">
                        {x.entidad} · {x.provincia}, {x.departamento} · {x.sector} · {fmtMillones(x.monto)}
                      </div>
                      <p className="mt-1 rounded-md bg-slate-50 p-2 text-xs text-slate-700">{mensajeCuaderno(x.score)}</p>
                      {x.factores && <div className="mt-1 text-xs text-slate-500">Factores: {x.factores.map((f) => f.descripcion).join(' · ')}</div>}
                    </div>
                    <div className="md:text-right">
                      <NivelBadge nivel={x.nivel} score={x.score} />
                    </div>
                  </li>
                ))}
                {rc.data?.items.length === 0 && <li className="py-3 text-sm text-slate-500">No hay obras en este nivel para el ámbito seleccionado.</li>}
              </ul>
            )
          ) : rk.isLoading ? (
            <Cargando />
          ) : (
            <ul className="divide-y divide-slate-100">
              {(rk.data?.items ?? []).map((x) => (
                <li key={x.codigo_infobras} className="grid gap-2 py-3 md:grid-cols-[1fr_auto]">
                  <div>
                    <Link to={`/cartera/${x.codigo_infobras}`} className="font-medium text-marca-700 hover:underline">
                      {x.nombre.slice(0, 180)}
                      {x.nombre.length > 180 ? '…' : ''}
                    </Link>
                    <div className="text-xs text-slate-500">
                      {x.entidad} · {x.provincia}, {x.departamento} · {x.tipo_obra} · {x.modalidad} · {fmtMillones(x.monto)} · fin programado {fmtFecha(x.fin_programado)}
                    </div>
                    <p className="mt-1 rounded-md bg-slate-50 p-2 text-xs text-slate-700">{mensajeCartera(x.score, x.modelo)}</p>
                    {x.factores && <div className="mt-1 text-xs text-slate-500">Factores: {x.factores.map((f) => f.descripcion).join(' · ')}</div>}
                  </div>
                  <div className="md:text-right">
                    <NivelBadge nivel={x.nivel} score={x.score} />
                  </div>
                </li>
              ))}
              {rk.data?.items.length === 0 && <li className="py-3 text-sm text-slate-500">No hay obras en este nivel para el ámbito seleccionado.</li>}
            </ul>
          )}
        </div>
      </section>

      <Seccion
        titulo="Cómo le habría ido al radar en el pasado (backtest as-of)"
        subtitulo="Para cada corte mensual: alertas emitidas solo con información disponible en esa fecha y cuántas se confirmaron con un atraso formal dentro de 60 días."
      >
        <div className="h-64">
          <ResponsiveContainer>
            <LineChart data={hist} margin={{ left: -10 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="mes" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line isAnimationActive={false} dataKey="alertas" name="Alertas emitidas (nivel alto)" stroke="#d97706" dot={false} strokeWidth={2} />
              <Line isAnimationActive={false} dataKey="alertas_confirmadas" name="Alertas confirmadas" stroke="#15803d" dot={false} strokeWidth={2} />
              <Line isAnimationActive={false} dataKey="eventos_observados" name="Atrasos formales observados" stroke="#b91c1c" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Seccion>
    </div>
  )
}
