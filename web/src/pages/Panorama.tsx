import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Building2, CalendarDays, ChevronRight, Coins, FileText, MapPin, Printer, Wallet } from 'lucide-react'
import { Tabs } from 'radix-ui'
import { useEffect, useMemo, useState } from 'react'
import { CircleMarker, MapContainer, TileLayer, Tooltip as MapTip, useMap } from 'react-leaflet'
import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, fmtDec, fmtFecha, fmtMes, fmtMillones, fmtNum, montoPartes, nombreObra, qs, titulo, useCalibracion, type Nivel } from '../api'
import { useAmbito } from '../ambito'
import { VistaPreviaCuaderno } from '../components/Factores'
import { CargandoPagina, Cargando, EncabezadoPagina, ErrorMsg, InfoTip, Kpi, NivelBadge, Panel, Seccion, Segmentado, Tendencia, Vacio } from '../components/ui'
import { COLOR_NIVEL, COLORES, SERIE } from '../lib/colores'
import { NIVEL_TEXTO } from '../lib/nivel'

interface Resumen {
  fecha_corte_cuaderno: string
  fecha_corte_cartera: string | null
  cuaderno: { activas: number; alto: number; medio: number; monto_activo: number; monto_alto: number }
  cartera: { activas: number; alto: number; medio: number; monto_activo: number; monto_alto: number; con_cuaderno: number }
  consolidado: { obras: number; en_ambos: number; monto: number; alto: number; monto_alto: number }
  distribucion: { ambito: string; evaluadas: number; alto: number }[]
  historico: { fecha_corte: string; evaluadas: number; alertas: number; alertas_confirmadas: number; eventos_observados: number; observables: number }[]
}
interface ItemC {
  prediccion_id: number
  cuaderno_id: string
  nombre: string
  departamento: string
  provincia: string
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

function Encuadre({ puntos, clave }: { puntos: Punto[]; clave: string }) {
  const map = useMap()
  useEffect(() => {
    if (!puntos.length) return
    const lats = puntos.map((p) => p.lat).sort((a, b) => a - b)
    const lons = puntos.map((p) => p.lon).sort((a, b) => a - b)
    const q = (a: number[], f: number) => a[Math.min(a.length - 1, Math.max(0, Math.floor(f * (a.length - 1))))]
    map.fitBounds(
      [
        [q(lats, 0.01), q(lons, 0.01)],
        [q(lats, 0.99), q(lons, 0.99)],
      ],
      { padding: [16, 16], maxZoom: 9 },
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clave])
  return null
}

function Mapa({ departamento }: { departamento: string | null }) {
  const [solo, setSolo] = useState<'ALTO' | 'todos'>('ALTO')
  const p = { departamento }
  const mc = useQuery({
    queryKey: ['mapa-c', departamento],
    queryFn: () => api<{ cuaderno_id: string; denominacion: string; latitud: number; longitud: number; nivel: Nivel; score: number }[]>(`/obras/mapa${qs(p)}`),
  })
  const mk = useQuery({
    queryKey: ['mapa-k', departamento],
    queryFn: () => api<{ codigo_infobras: string; nombre: string; latitud: number; longitud: number; nivel: Nivel; score: number }[]>(`/cartera/mapa${qs(p)}`),
  })
  const puntos = useMemo<Punto[]>(
    () => [
      ...(mk.data ?? []).map((x) => ({ id: x.codigo_infobras, nombre: x.nombre, lat: x.latitud, lon: x.longitud, nivel: x.nivel, score: x.score, tipo: 'cartera' as const })),
      ...(mc.data ?? []).map((x) => ({ id: x.cuaderno_id, nombre: x.denominacion, lat: x.latitud, lon: x.longitud, nivel: x.nivel, score: x.score, tipo: 'cuaderno' as const })),
    ],
    [mc.data, mk.data],
  )
  const visibles = solo === 'ALTO' ? puntos.filter((x) => x.nivel === 'ALTO') : puntos
  const orden: Record<string, number> = { BAJO: 0, MEDIO: 1, ALTO: 2 }
  const dibujo = [...visibles].sort((a, b) => (orden[a.nivel ?? 'BAJO'] ?? 0) - (orden[b.nivel ?? 'BAJO'] ?? 0))
  return (
    <div className="mapa-sobrio relative h-full min-h-[440px] overflow-hidden rounded-lg border border-slate-200">
      {(mc.isLoading || mk.isLoading) && <div className="esqueleto absolute inset-0 z-[500]" />}
      <MapContainer center={[-9.2, -75.0]} zoom={5} scrollWheelZoom={false} preferCanvas className="h-full w-full">
        <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <Encuadre puntos={puntos} clave={`${departamento ?? 'PE'}-${puntos.length}`} />
        {dibujo.map((x) => (
          <CircleMarker
            key={x.tipo + x.id}
            center={[x.lat, x.lon]}
            radius={x.nivel === 'ALTO' ? 6 : x.nivel === 'MEDIO' ? 4.5 : 3.5}
            pathOptions={{ color: '#ffffff', weight: 1.2, fillColor: x.nivel ? COLOR_NIVEL[x.nivel] : COLORES.gris, fillOpacity: 0.9 }}
          >
            <MapTip>
              <div className="max-w-64 text-xs">
                <b>{nombreObra(x.nombre).slice(0, 110)}</b>
                <br />
                {x.tipo === 'cuaderno' ? 'Alerta a 60 días (cuaderno digital)' : 'Riesgo al término (cartera INFOBRAS)'} · riesgo {x.nivel ? NIVEL_TEXTO[x.nivel].toLowerCase() : '—'}
              </div>
            </MapTip>
          </CircleMarker>
        ))}
      </MapContainer>
      <div className="absolute top-3 right-3 z-[500]">
        <Segmentado
          etiqueta="Obras en el mapa"
          valor={solo}
          onChange={setSolo}
          opciones={[
            { v: 'ALTO', l: 'Solo riesgo alto' },
            { v: 'todos', l: 'Todas' },
          ]}
        />
      </div>
      <div className="absolute bottom-3 left-3 z-[500] flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg bg-white/95 px-3 py-2 text-sm text-slate-700 shadow-sm ring-1 ring-slate-200">
        {(['ALTO', 'MEDIO', 'BAJO'] as Nivel[]).map((n) => (
          <span key={n} className="flex items-center gap-1.5">
            <span className="size-3 rounded-full ring-2 ring-white" style={{ background: COLOR_NIVEL[n] }} aria-hidden /> {NIVEL_TEXTO[n]}
          </span>
        ))}
        <span className="num font-medium text-slate-600">{fmtNum(visibles.length)} obras</span>
      </div>
    </div>
  )
}

function FilaObra({ i, nombre, lugar, factor, nivel, score, onClick }: { i: number; nombre: string; lugar: string; factor?: string; nivel: Nivel; score: number; onClick: () => void }) {
  return (
    <li>
      <button className="group flex w-full items-start gap-3 px-4 py-3.5 text-left transition-colors duration-150 hover:bg-marca-50/60 sm:px-5" onClick={onClick}>
        <span className="num mt-0.5 w-5 shrink-0 text-right text-sm font-semibold text-slate-500">{i + 1}</span>
        <span className="min-w-0 flex-1">
          <span className="line-clamp-2 font-semibold text-slate-900 group-hover:text-marca-800" title={nombre}>
            {nombreObra(nombre)}
          </span>
          <span className="mt-0.5 block truncate text-sm text-slate-600">{lugar}</span>
          {factor && <span className="mt-1.5 line-clamp-2 text-sm text-slate-700">Principal factor: {factor}</span>}
        </span>
        <span className="flex shrink-0 items-center gap-1">
          <NivelBadge nivel={nivel} score={score} compacto />
          <ChevronRight className="size-4 text-slate-400 transition-colors group-hover:text-marca-700" aria-hidden />
        </span>
      </button>
    </li>
  )
}

function Prioridad({ departamento, total }: { departamento: string | null; total: { cuaderno: number; cartera: number } }) {
  const [tab, setTab] = useState<'cuaderno' | 'cartera'>('cuaderno')
  const [sel, setSel] = useState<ItemC | null>(null)
  const [selK, setSelK] = useState<ItemK | null>(null)
  const p = { departamento, nivel: 'ALTO', limite: 8 }
  const rc = useQuery({ queryKey: ['radar-c', p], queryFn: () => api<{ items: ItemC[] }>(`/radar/cuaderno${qs(p)}`) })
  const rk = useQuery({ queryKey: ['radar-k', p], queryFn: () => api<{ items: ItemK[] }>(`/radar/cartera${qs(p)}`), enabled: tab === 'cartera' })
  const q = tab === 'cuaderno' ? rc : rk
  return (
    <Seccion
      className="flex h-full flex-col overflow-hidden"
      cuerpo="flex flex-col"
      titulo="Obras que requieren atención"
      subtitulo="Obras en ejecución con mayor probabilidad estimada. Seleccione una para ver por qué."
      sinRelleno
      accion={
        <Segmentado
          etiqueta="Modelo"
          valor={tab}
          onChange={setTab}
          opciones={[
            { v: 'cuaderno', l: 'Atraso en 60 días' },
            { v: 'cartera', l: 'Retraso al término' },
          ]}
        />
      }
    >
      {q.isLoading ? (
        <div className="p-4">
          <Cargando filas={6} />
        </div>
      ) : q.error ? (
        <div className="p-4">
          <ErrorMsg error={q.error} reintentar={() => q.refetch()} />
        </div>
      ) : tab === 'cuaderno' ? (
        rc.data!.items.length === 0 ? (
          <Vacio titulo="Ninguna obra en riesgo alto" texto="No hay obras con cuaderno digital en riesgo alto en el ámbito seleccionado." />
        ) : (
          <ol className="flex-1 divide-y divide-slate-100 overflow-y-auto">
            {rc.data!.items.map((x, i) => (
              <FilaObra
                key={x.prediccion_id}
                i={i}
                nombre={x.nombre}
                lugar={`${titulo(x.provincia)}, ${titulo(x.departamento)} · ${x.entidad}`}
                factor={x.factores?.[0]?.descripcion}
                nivel={x.nivel}
                score={x.score}
                onClick={() => setSel(x)}
              />
            ))}
          </ol>
        )
      ) : rk.data!.items.length === 0 ? (
        <Vacio titulo="Ninguna obra en riesgo alto" texto="No hay obras de la cartera en riesgo alto en el ámbito seleccionado." />
      ) : (
        <ol className="flex-1 divide-y divide-slate-100 overflow-y-auto">
          {rk.data!.items.map((x, i) => (
            <FilaObra
              key={x.codigo_infobras}
              i={i}
              nombre={x.nombre}
              lugar={`${titulo(x.provincia)}, ${titulo(x.departamento)} · ${x.modalidad} · ${fmtMillones(x.monto)}`}
              factor={x.factores?.[0]?.descripcion}
              nivel={x.nivel}
              score={x.score}
              onClick={() => setSelK(x)}
            />
          ))}
        </ol>
      )}
      <div className="border-t border-slate-100 px-4 py-3 sm:px-5">
        <Link to={tab === 'cuaderno' ? '/obras?nivel=ALTO' : '/cartera?nivel=ALTO'} className="enlace inline-flex items-center gap-1.5 text-sm">
          Ver las {fmtNum(tab === 'cuaderno' ? total.cuaderno : total.cartera)} obras en riesgo alto <ArrowRight className="size-4" aria-hidden />
        </Link>
      </div>
      <Panel abierto={!!sel} onClose={() => setSel(null)} titulo="Vista previa de la alerta" subtitulo="Resumen de la predicción vigente y sus principales factores">
        {sel && <VistaPreviaCuaderno prediccionId={sel.prediccion_id} cuadernoId={sel.cuaderno_id} nombre={nombreObra(sel.nombre)} />}
      </Panel>
      <Panel abierto={!!selK} onClose={() => setSelK(null)} titulo="Vista previa del riesgo" subtitulo="Cartera INFOBRAS: probabilidad de terminar con retraso significativo">
        {selK && (
          <div className="space-y-5">
            <div className="font-display text-base font-semibold text-slate-900">{nombreObra(selK.nombre)}</div>
            <div className="rounded-xl border border-slate-200 p-4">
              <NivelBadge nivel={selK.nivel} score={selK.score} />
              <p className="mt-2 text-sm text-slate-700">
                Estimación del modelo {selK.modelo === 'seguimiento' ? 'de seguimiento mensual (incluye la ejecución del gasto)' : 'al inicio de la obra'}. Fin programado:{' '}
                {fmtFecha(selK.fin_programado)}.
              </p>
            </div>
            <div>
              <div className="etiqueta mb-2">Qué eleva el riesgo</div>
              <ul className="list-disc space-y-1.5 pl-5 text-sm text-slate-800">
                {(selK.factores ?? []).map((f) => (
                  <li key={f.descripcion}>{f.descripcion}</li>
                ))}
              </ul>
            </div>
            <Link to={`/cartera/${selK.codigo_infobras}`} className="btn-primario">
              Ver ficha completa <ArrowRight className="size-4" aria-hidden />
            </Link>
          </div>
        )}
      </Panel>
    </Seccion>
  )
}

function Distribucion({ datos, departamento }: { datos: Resumen['distribucion']; departamento: string | null }) {
  const [vista, setVista] = useState<'grafico' | 'tabla'>('grafico')
  const d = datos.slice(0, 25).map((x) => ({ ...x, ambito: titulo(x.ambito) }))
  const unidad = departamento ? 'Provincia' : 'Departamento'
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-slate-600">Obras con cuaderno digital evaluadas en el corte vigente y cuántas están en riesgo alto.</p>
        <Segmentado etiqueta="Vista de la distribución" valor={vista} onChange={setVista} opciones={[{ v: 'grafico', l: 'Gráfico' }, { v: 'tabla', l: 'Tabla' }]} />
      </div>
      {vista === 'grafico' ? (
        <div style={{ height: Math.max(300, d.length * 20 + 50) }} role="img" aria-label={`Obras evaluadas y en riesgo alto por ${unidad.toLowerCase()}`}>
          <ResponsiveContainer>
            <BarChart data={d} layout="vertical" margin={{ left: 4, right: 16, top: 4, bottom: 4 }} barGap={2}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke={COLORES.rejilla} />
              <XAxis type="number" tick={{ fontSize: 12 }} />
              <YAxis dataKey="ambito" type="category" tick={{ fontSize: 12 }} width={116} interval={0} />
              <Tooltip cursor={{ fill: '#eef3f8' }} />
              <Legend wrapperStyle={{ fontSize: 13 }} />
              <Bar isAnimationActive={false} dataKey="evaluadas" name="Obras evaluadas" fill={SERIE[0]} radius={[0, 4, 4, 0]} />
              <Bar isAnimationActive={false} dataKey="alto" name="En riesgo alto" fill={COLOR_NIVEL.ALTO} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="max-h-[440px] overflow-auto rounded-lg border border-slate-200">
          <table className="tabla">
            <thead>
              <tr>
                <th>{unidad}</th>
                <th className="text-right">Evaluadas</th>
                <th className="text-right">Riesgo alto</th>
                <th className="text-right">Proporción</th>
              </tr>
            </thead>
            <tbody>
              {d.map((x) => (
                <tr key={x.ambito}>
                  <td className="font-medium text-slate-900">{x.ambito}</td>
                  <td className="num text-right">{fmtNum(x.evaluadas)}</td>
                  <td className="num text-right">{fmtNum(x.alto)}</td>
                  <td className="num text-right">{x.evaluadas ? `${fmtDec((100 * x.alto) / x.evaluadas, 1)} %` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function Confiabilidad({ historico }: { historico: Resumen['historico'] }) {
  const c = useCalibracion()
  const [vista, setVista] = useState<'grafico' | 'tabla'>('grafico')
  // solo cortes cuyo resultado a 60 días ya es observable: los más recientes aún no pueden confirmarse
  const hist = historico.filter((h) => h.observables > 0 && h.observables === h.evaluadas).map((h) => ({ ...h, mes: fmtMes(h.fecha_corte) }))
  const niveles = c.data?.alerta_60d.niveles ?? []
  const maxTasa = Math.max(...niveles.map((m) => m.tasa_observada), 0.0001)
  return (
    <Seccion
      titulo="¿Qué tan confiables son las alertas?"
      ayuda="backtest"
      subtitulo="Simulación con datos pasados: cada mes se estimó el riesgo solo con la información de esa fecha y luego se comparó con lo ocurrido."
      accion={
        <Link to="/laboratorio" className="btn btn-sm">
          Ver validación completa
        </Link>
      }
    >
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-5">
        <div className="lg:col-span-2">
          <h3 className="text-base font-semibold text-slate-900">Resultado real de cada nivel</h3>
          <p className="mt-1 text-sm text-slate-600">Obras de cada nivel que registraron el atraso formal en los 60 días siguientes.</p>
          <ul className="mt-4 space-y-4">
            {niveles.map((n) => (
              <li key={n.nivel} className="grid grid-cols-[6.5rem_1fr] items-center gap-3">
                <NivelBadge nivel={n.nivel} compacto />
                <div>
                  <div className="flex items-baseline justify-between gap-2 text-sm">
                    <span className="num text-slate-800">
                      <b className="font-display text-lg">{Math.round(100 * n.tasa_observada)}</b> de cada 100
                    </span>
                  </div>
                  <div className="mt-1 flex h-2.5 overflow-hidden rounded-full bg-slate-100">
                    <div className="h-full rounded-full" style={{ width: `${(100 * n.tasa_observada) / maxTasa}%`, background: COLOR_NIVEL[n.nivel] }} />
                  </div>
                </div>
              </li>
            ))}
          </ul>
          {c.data && (
            <p className="mt-5 rounded-lg bg-slate-50 p-3.5 text-sm leading-relaxed text-slate-700">
              Promedio general: <b>{Math.round(100 * c.data.alerta_60d.tasa_base)} de cada 100</b> obras-mes. Revisar primero las obras en riesgo alto multiplica por{' '}
              <b>{niveles[0] ? fmtDec(niveles[0].tasa_observada / c.data.alerta_60d.tasa_base, 1) : '—'}</b> la probabilidad de encontrar un atraso frente a una selección al azar
              (periodo {fmtMes(c.data.alerta_60d.desde)} a {fmtMes(c.data.alerta_60d.hasta)}; {fmtNum(c.data.alerta_60d.n)} observaciones).
            </p>
          )}
        </div>
        <div className="lg:col-span-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-base font-semibold text-slate-900">Alertas y atrasos por corte mensual</h3>
            <Segmentado etiqueta="Vista del historial" valor={vista} onChange={setVista} opciones={[{ v: 'grafico', l: 'Gráfico' }, { v: 'tabla', l: 'Tabla' }]} />
          </div>
          {vista === 'grafico' ? (
            <div className="mt-3 h-64" role="img" aria-label="Alertas emitidas, atrasos ocurridos y alertas confirmadas por corte mensual">
              <ResponsiveContainer>
                <LineChart data={hist} margin={{ left: -12, right: 12, top: 6 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={COLORES.rejilla} />
                  <XAxis dataKey="mes" tick={{ fontSize: 12 }} minTickGap={20} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: 13 }} />
                  <Line isAnimationActive={false} dataKey="alertas" name="Alertas emitidas (riesgo alto)" stroke={SERIE[0]} dot={false} strokeWidth={2} />
                  <Line isAnimationActive={false} dataKey="eventos_observados" name="Atrasos formales ocurridos" stroke={SERIE[1]} dot={false} strokeWidth={2} />
                  <Line isAnimationActive={false} dataKey="alertas_confirmadas" name="Alertas confirmadas" stroke={SERIE[2]} dot={{ r: 2.5 }} strokeWidth={2} strokeDasharray="5 3" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="mt-3 max-h-64 overflow-auto rounded-lg border border-slate-200">
              <table className="tabla">
                <thead>
                  <tr>
                    <th>Corte</th>
                    <th className="text-right">Alertas emitidas</th>
                    <th className="text-right">Atrasos ocurridos</th>
                    <th className="text-right">Alertas confirmadas</th>
                  </tr>
                </thead>
                <tbody>
                  {[...hist].reverse().map((h) => (
                    <tr key={h.fecha_corte}>
                      <td>{h.mes}</td>
                      <td className="num text-right">{fmtNum(h.alertas)}</td>
                      <td className="num text-right">{fmtNum(h.eventos_observados)}</td>
                      <td className="num text-right">{fmtNum(h.alertas_confirmadas)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </Seccion>
  )
}

function Meta({ icono, children }: { icono: React.ReactNode; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1 text-sm text-slate-700">
      {icono}
      {children}
    </span>
  )
}

export default function Panorama() {
  const { departamento } = useAmbito()
  const r = useQuery({ queryKey: ['resumen', departamento], queryFn: () => api<Resumen>(`/resumen${qs({ departamento })}`) })
  if (r.isLoading) return <CargandoPagina />
  if (r.error) return <ErrorMsg error={r.error} reintentar={() => r.refetch()} />
  const d = r.data!
  const ambito = departamento ? titulo(departamento) : 'todo el Perú'
  const inv = montoPartes(d.consolidado.monto)
  const invAlto = montoPartes(d.consolidado.monto_alto)
  const serieAlertas = d.historico.map((h) => h.alertas)
  return (
    <div className="space-y-6">
      <EncabezadoPagina
        titulo="Panorama de riesgo"
        antes={
          <div className="mb-3 flex flex-wrap gap-2">
            <Meta icono={<MapPin className="size-3.5 text-marca-600" aria-hidden />}>{departamento ? titulo(departamento) : 'Todo el Perú'}</Meta>
            <Meta icono={<CalendarDays className="size-3.5 text-marca-600" aria-hidden />}>Cuaderno digital al {fmtFecha(d.fecha_corte_cuaderno)}</Meta>
            <Meta icono={<CalendarDays className="size-3.5 text-marca-600" aria-hidden />}>Cartera INFOBRAS al {fmtFecha(d.fecha_corte_cartera)}</Meta>
          </div>
        }
        descripcion="Obras públicas en ejecución y su riesgo estimado de atraso, calculado solo con datos abiertos oficiales."
        acciones={
          <button className="btn" onClick={() => window.print()}>
            <Printer className="size-4" aria-hidden />
            Imprimir resumen
          </button>
        }
      />
      <section aria-label="Resumen" className="tarjeta border-l-4 border-l-marca-600 px-5 py-4">
        <p className="text-base leading-relaxed text-slate-800">
          En {ambito}, <b className="num">{fmtNum(d.cuaderno.alto)}</b> obras con cuaderno digital tienen <b>riesgo alto de registrar un atraso formal en los próximos 60 días</b> y{' '}
          <b className="num">{fmtNum(d.cartera.alto)}</b> obras de la cartera INFOBRAS tienen <b>riesgo alto de terminar con retraso significativo</b>. Son estimaciones para priorizar
          la supervisión, no certezas.
        </p>
        <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-sm">
          <Link to="/obras?nivel=ALTO" className="enlace inline-flex items-center gap-1">
            Revisar alertas del cuaderno <ArrowRight className="size-4" aria-hidden />
          </Link>
          <Link to="/cartera?nivel=ALTO&estado=ACTIVA" className="enlace inline-flex items-center gap-1">
            Revisar la cartera en riesgo alto <ArrowRight className="size-4" aria-hidden />
          </Link>
        </div>
      </section>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi
          titulo="Obras en ejecución monitoreadas"
          icono={<Building2 className="size-4" aria-hidden />}
          valor={fmtNum(d.consolidado.obras)}
          unidad="obras"
          detalle={`${fmtNum(d.cuaderno.activas)} con cuaderno digital y ${fmtNum(d.cartera.activas)} en la cartera INFOBRAS (${fmtNum(d.consolidado.en_ambos)} en ambas, contadas una vez).`}
        />
        <Kpi titulo="Inversión monitoreada" icono={<Wallet className="size-4" aria-hidden />} valor={inv.valor} unidad={inv.unidad} detalle="Monto del contrato o costo de obra de las obras en ejecución evaluadas." />
        <Kpi
          titulo="Riesgo alto de atraso en 60 días"
          icono={<FileText className="size-4" aria-hidden />}
          tono="alto"
          ayuda="atraso_formal"
          valor={fmtNum(d.cuaderno.alto)}
          unidad={`de ${fmtNum(d.cuaderno.activas)} obras con cuaderno`}
          tendencia={<Tendencia valores={serieAlertas} tono="alto" etiqueta={`Obras en riesgo alto por corte mensual: de ${fmtNum(serieAlertas[0])} a ${fmtNum(serieAlertas[serieAlertas.length - 1])}`} />}
          detalle={`${fmtNum(d.cuaderno.medio)} obras más en riesgo medio. La línea muestra las obras en riesgo alto de cada corte mensual.`}
        />
        <Kpi
          titulo="Inversión en obras de riesgo alto"
          icono={<Coins className="size-4" aria-hidden />}
          tono="alto"
          valor={invAlto.valor}
          unidad={invAlto.unidad}
          detalle={`${fmtNum(d.consolidado.alto)} obras en riesgo alto en al menos un modelo. Es el monto comprometido, no una pérdida estimada.`}
        />
      </div>
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
        <div className="xl:col-span-5 xl:h-[640px]">
          <Prioridad departamento={departamento} total={{ cuaderno: d.cuaderno.alto, cartera: d.cartera.alto }} />
        </div>
        <div className="xl:col-span-7 xl:h-[640px]">
          <Tabs.Root defaultValue="mapa" className="tarjeta flex h-full flex-col">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 pt-1 sm:px-5">
              <Tabs.List className="flex gap-1" aria-label="Vista territorial">
                <Tabs.Trigger value="mapa" className="pestana">
                  Mapa de riesgo
                </Tabs.Trigger>
                <Tabs.Trigger value="distribucion" className="pestana">
                  {departamento ? 'Por provincia' : 'Por departamento'}
                </Tabs.Trigger>
              </Tabs.List>
              <InfoTip texto="Ubicación referencial de cada obra (coordenadas del cuaderno digital o de la inversión en el Banco de Inversiones). El color y el tamaño indican el nivel de riesgo vigente." />
            </div>
            <Tabs.Content value="mapa" className="flex-1 p-4 data-[state=inactive]:hidden sm:p-5">
              <Mapa departamento={departamento} />
            </Tabs.Content>
            <Tabs.Content value="distribucion" className="overflow-y-auto p-4 sm:p-5">
              <Distribucion datos={d.distribucion} departamento={departamento} />
            </Tabs.Content>
          </Tabs.Root>
        </div>
      </div>
      <Confiabilidad historico={d.historico} />
    </div>
  )
}
