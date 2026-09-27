import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, ArrowRight, Building2, ChevronRight, Coins, FileText, Wallet } from 'lucide-react'
import { Tabs } from 'radix-ui'
import { useEffect, useMemo, useState } from 'react'
import { CircleMarker, MapContainer, TileLayer, Tooltip as MapTip, useMap } from 'react-leaflet'
import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, fmtDec, fmtFecha, fmtMes, fmtMillones, fmtNum, qs, titulo, useCalibracion, type Nivel } from '../api'
import { useAmbito } from '../ambito'
import { VistaPreviaCuaderno } from '../components/Factores'
import { CargandoPagina, Cargando, EncabezadoPagina, ErrorMsg, InfoTip, Kpi, NivelBadge, Panel, Seccion, Segmentado, Vacio } from '../components/ui'
import { COLOR_NIVEL, COLORES } from '../lib/colores'
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
    <div className="relative h-full min-h-[420px] overflow-hidden rounded-lg border border-slate-200">
      {(mc.isLoading || mk.isLoading) && <div className="esqueleto absolute inset-0 z-[500]" />}
      <MapContainer center={[-9.2, -75.0]} zoom={5} scrollWheelZoom={false} preferCanvas className="h-full w-full">
        <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <Encuadre puntos={puntos} clave={`${departamento ?? 'PE'}-${puntos.length}`} />
        {dibujo.map((x) => (
          <CircleMarker
            key={x.tipo + x.id}
            center={[x.lat, x.lon]}
            radius={x.nivel === 'ALTO' ? 5.5 : x.nivel === 'MEDIO' ? 4 : 3}
            pathOptions={{ color: '#fff', weight: 0.6, fillColor: x.nivel ? COLOR_NIVEL[x.nivel] : COLORES.gris, fillOpacity: 0.85 }}
          >
            <MapTip>
              <div className="max-w-64 text-xs">
                <b>{x.nombre.slice(0, 110)}</b>
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
      <div className="absolute bottom-3 left-3 z-[500] flex gap-3 rounded-lg bg-white/95 px-3 py-2 text-xs text-slate-600 shadow-sm">
        {(['ALTO', 'MEDIO', 'BAJO'] as Nivel[]).map((n) => (
          <span key={n} className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-full" style={{ background: COLOR_NIVEL[n] }} /> {NIVEL_TEXTO[n]}
          </span>
        ))}
        <span className="num text-slate-400">{fmtNum(visibles.length)} obras</span>
      </div>
    </div>
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
          <ol className="divide-y divide-slate-100 xl:max-h-[372px] xl:overflow-y-auto">
            {rc.data!.items.map((x, i) => (
              <li key={x.prediccion_id}>
                <button className="group flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-slate-50" onClick={() => setSel(x)}>
                  <span className="num mt-0.5 w-5 shrink-0 text-right text-xs font-medium text-slate-400">{i + 1}</span>
                  <span className="min-w-0 flex-1">
                    <span className="line-clamp-2 text-sm font-medium text-slate-900 group-hover:text-marca-700">{x.nombre}</span>
                    <span className="mt-0.5 block truncate text-xs text-slate-500">
                      {titulo(x.provincia)}, {titulo(x.departamento)} · {x.entidad}
                    </span>
                    {x.factores?.[0] && <span className="mt-1 line-clamp-2 text-xs text-slate-600">Principal factor: {x.factores[0].descripcion}</span>}
                  </span>
                  <span className="flex shrink-0 items-center gap-1">
                    <NivelBadge nivel={x.nivel} score={x.score} compacto />
                    <ChevronRight className="size-4 text-slate-300 group-hover:text-slate-500" />
                  </span>
                </button>
              </li>
            ))}
          </ol>
        )
      ) : rk.data!.items.length === 0 ? (
        <Vacio titulo="Ninguna obra en riesgo alto" texto="No hay obras de la cartera en riesgo alto en el ámbito seleccionado." />
      ) : (
        <ol className="divide-y divide-slate-100 xl:max-h-[372px] xl:overflow-y-auto">
          {rk.data!.items.map((x, i) => (
            <li key={x.codigo_infobras}>
              <button className="group flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-slate-50" onClick={() => setSelK(x)}>
                <span className="num mt-0.5 w-5 shrink-0 text-right text-xs font-medium text-slate-400">{i + 1}</span>
                <span className="min-w-0 flex-1">
                  <span className="line-clamp-2 text-sm font-medium text-slate-900 group-hover:text-marca-700">{x.nombre}</span>
                  <span className="mt-0.5 block truncate text-xs text-slate-500">
                    {titulo(x.provincia)}, {titulo(x.departamento)} · {x.modalidad} · {fmtMillones(x.monto)}
                  </span>
                  {x.factores?.[0] && <span className="mt-1 line-clamp-2 text-xs text-slate-600">Principal factor: {x.factores[0].descripcion}</span>}
                </span>
                <span className="flex shrink-0 items-center gap-1">
                  <NivelBadge nivel={x.nivel} score={x.score} compacto />
                  <ChevronRight className="size-4 text-slate-300 group-hover:text-slate-500" />
                </span>
              </button>
            </li>
          ))}
        </ol>
      )}
      <div className="border-t border-slate-100 px-4 py-3">
        <Link to={tab === 'cuaderno' ? '/obras?nivel=ALTO' : '/cartera?nivel=ALTO'} className="enlace inline-flex items-center gap-1 text-sm">
          Ver las {fmtNum(tab === 'cuaderno' ? total.cuaderno : total.cartera)} obras en riesgo alto <ArrowRight className="size-4" />
        </Link>
      </div>
      <Panel abierto={!!sel} onClose={() => setSel(null)} titulo="Vista previa de la alerta" subtitulo="Resumen de la predicción vigente y sus principales factores">
        {sel && <VistaPreviaCuaderno prediccionId={sel.prediccion_id} cuadernoId={sel.cuaderno_id} nombre={sel.nombre} />}
      </Panel>
      <Panel abierto={!!selK} onClose={() => setSelK(null)} titulo="Vista previa del riesgo" subtitulo="Cartera INFOBRAS: probabilidad de terminar con retraso significativo">
        {selK && (
          <div className="space-y-4">
            <div className="text-sm font-medium text-slate-900">{selK.nombre}</div>
            <div className="rounded-xl border border-slate-200 p-4">
              <NivelBadge nivel={selK.nivel} score={selK.score} />
              <p className="mt-2 text-sm text-slate-600">
                Estimación del modelo {selK.modelo === 'seguimiento' ? 'de seguimiento mensual (incluye la ejecución del gasto)' : 'al inicio de la obra'}. Fin programado:{' '}
                {fmtFecha(selK.fin_programado)}.
              </p>
            </div>
            <div>
              <div className="etiqueta mb-1">Qué eleva el riesgo</div>
              <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
                {(selK.factores ?? []).map((f) => (
                  <li key={f.descripcion}>{f.descripcion}</li>
                ))}
              </ul>
            </div>
            <Link to={`/cartera/${selK.codigo_infobras}`} className="btn-primario">
              Ver ficha completa <ArrowRight className="size-4" />
            </Link>
          </div>
        )}
      </Panel>
    </Seccion>
  )
}

function Distribucion({ datos, departamento }: { datos: Resumen['distribucion']; departamento: string | null }) {
  const d = datos.slice(0, 25).map((x) => ({ ...x, ambito: titulo(x.ambito) }))
  return (
    <div style={{ height: Math.max(300, d.length * 17 + 40) }}>
      <ResponsiveContainer>
        <BarChart data={d} layout="vertical" margin={{ left: 4, right: 12, top: 4, bottom: 4 }} barGap={1}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke={COLORES.rejilla} />
          <XAxis type="number" tick={{ fontSize: 11 }} />
          <YAxis dataKey="ambito" type="category" tick={{ fontSize: 11 }} width={108} interval={0} />
          <Tooltip cursor={{ fill: '#f1f5f9' }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar isAnimationActive={false} dataKey="evaluadas" name={departamento ? 'Obras evaluadas por provincia' : 'Obras evaluadas'} fill={COLORES.marca} radius={[0, 3, 3, 0]} />
          <Bar isAnimationActive={false} dataKey="alto" name="En riesgo alto" fill={COLOR_NIVEL.ALTO} radius={[0, 3, 3, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function Confiabilidad({ historico }: { historico: Resumen['historico'] }) {
  const c = useCalibracion()
  // solo cortes cuyo resultado a 60 días ya es observable: los más recientes aún no pueden confirmarse
  const hist = historico.filter((h) => h.observables > 0 && h.observables === h.evaluadas).map((h) => ({ ...h, mes: fmtMes(h.fecha_corte) }))
  const niveles = c.data?.alerta_60d.niveles ?? []
  return (
    <Seccion
      titulo="¿Qué tan confiables son las alertas?"
      ayuda="backtest"
      subtitulo="Simulación con datos pasados: cada mes se estimó el riesgo solo con la información de esa fecha y luego se comparó con lo ocurrido. A la izquierda, cuántas obras de cada nivel registraron el atraso formal en 60 días."
      accion={
        <Link to="/laboratorio" className="btn btn-sm">
          Ver validación completa
        </Link>
      }
    >
      <div className="grid gap-5 lg:grid-cols-5">
        <div className="space-y-3 lg:col-span-2">
          {niveles.map((n) => (
            <div key={n.nivel} className="flex items-center gap-3">
              <span className="w-24 shrink-0">
                <NivelBadge nivel={n.nivel} compacto />
              </span>
              <div className="flex-1">
                <div className="flex h-2 overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full rounded-full" style={{ width: `${(100 * n.tasa_observada) / Math.max(...niveles.map((m) => m.tasa_observada))}%`, background: COLOR_NIVEL[n.nivel] }} />
                </div>
              </div>
              <span className="num w-28 shrink-0 text-sm text-slate-700">
                <b>{Math.round(100 * n.tasa_observada)}</b> de cada 100
              </span>
            </div>
          ))}
          {c.data && (
            <p className="text-[13px] leading-relaxed text-slate-500">
              Promedio general: {Math.round(100 * c.data.alerta_60d.tasa_base)} de cada 100 obras-mes. Periodo evaluado: {fmtMes(c.data.alerta_60d.desde)} a {fmtMes(c.data.alerta_60d.hasta)} (
              {fmtNum(c.data.alerta_60d.n)} observaciones). Revisar primero las obras en riesgo alto multiplica por{' '}
              {niveles[0] ? fmtDec(niveles[0].tasa_observada / c.data.alerta_60d.tasa_base, 1) : '—'} la probabilidad de encontrar un atraso frente a una
              selección al azar.
            </p>
          )}
        </div>
        <div className="h-56 lg:col-span-3">
          <ResponsiveContainer>
            <LineChart data={hist} margin={{ left: -18, right: 8, top: 4 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={COLORES.rejilla} />
              <XAxis dataKey="mes" tick={{ fontSize: 11 }} minTickGap={16} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line isAnimationActive={false} dataKey="alertas" name="Alertas emitidas (riesgo alto)" stroke={COLOR_NIVEL.MEDIO} dot={false} strokeWidth={2} />
              <Line isAnimationActive={false} dataKey="alertas_confirmadas" name="Alertas confirmadas" stroke={COLOR_NIVEL.BAJO} dot={false} strokeWidth={2} />
              <Line isAnimationActive={false} dataKey="eventos_observados" name="Atrasos formales ocurridos" stroke={COLOR_NIVEL.ALTO} dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </Seccion>
  )
}

export default function Panorama() {
  const { departamento } = useAmbito()
  const r = useQuery({ queryKey: ['resumen', departamento], queryFn: () => api<Resumen>(`/resumen${qs({ departamento })}`) })
  if (r.isLoading) return <CargandoPagina />
  if (r.error) return <ErrorMsg error={r.error} reintentar={() => r.refetch()} />
  const d = r.data!
  const ambito = departamento ? titulo(departamento) : 'todo el Perú'
  return (
    <div className="space-y-5">
      <EncabezadoPagina
        titulo={`Panorama de riesgo · ${departamento ? titulo(departamento) : 'Perú'}`}
        descripcion={`Obras públicas en ejecución y su riesgo estimado. Cuaderno de obra digital al ${fmtFecha(d.fecha_corte_cuaderno)}; cartera INFOBRAS con registros hasta el ${fmtFecha(d.fecha_corte_cartera)}.`}
      />
      <div className="flex items-start gap-3 rounded-xl border border-marca-100 bg-marca-50 px-4 py-3 text-sm leading-relaxed text-marca-900">
        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-marca-600" />
        <p>
          En {ambito}, <b className="num">{fmtNum(d.cuaderno.alto)}</b> obras con cuaderno digital tienen <b>riesgo alto de registrar un atraso formal en los próximos 60 días</b> y{' '}
          <b className="num">{fmtNum(d.cartera.alto)}</b> obras de la cartera INFOBRAS tienen <b>riesgo alto de terminar con retraso significativo</b>. Son estimaciones para
          priorizar la supervisión, no certezas.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi
          titulo="Obras en ejecución monitoreadas"
          icono={<Building2 className="size-4" />}
          valor={fmtNum(d.consolidado.obras)}
          detalle={`${fmtNum(d.cuaderno.activas)} con cuaderno digital y ${fmtNum(d.cartera.activas)} en la cartera INFOBRAS (${fmtNum(d.consolidado.en_ambos)} en ambas, contadas una vez).`}
        />
        <Kpi
          titulo="Inversión monitoreada"
          icono={<Wallet className="size-4" />}
          valor={fmtMillones(d.consolidado.monto ?? 0)}
          detalle="Monto del contrato o costo de obra de las obras en ejecución evaluadas."
        />
        <Kpi
          titulo="Riesgo alto de atraso en 60 días"
          icono={<FileText className="size-4" />}
          tono="alto"
          ayuda="atraso_formal"
          valor={fmtNum(d.cuaderno.alto)}
          detalle={`De ${fmtNum(d.cuaderno.activas)} obras con cuaderno digital; ${fmtNum(d.cuaderno.medio)} más en riesgo medio.`}
        />
        <Kpi
          titulo="Inversión en obras de riesgo alto"
          icono={<Coins className="size-4" />}
          tono="alto"
          valor={fmtMillones(d.consolidado.monto_alto ?? 0)}
          detalle={`${fmtNum(d.consolidado.alto)} obras en riesgo alto en al menos un modelo. Es el monto comprometido, no una pérdida estimada.`}
        />
      </div>
      <div className="grid gap-5 xl:grid-cols-12">
        <div className="xl:col-span-5 xl:h-[600px]">
          <Prioridad departamento={departamento} total={{ cuaderno: d.cuaderno.alto, cartera: d.cartera.alto }} />
        </div>
        <div className="xl:col-span-7 xl:h-[600px]">
          <Tabs.Root defaultValue="mapa" className="tarjeta flex h-full flex-col">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 pt-2">
              <Tabs.List className="flex gap-1" aria-label="Vista territorial">
                <Tabs.Trigger value="mapa" className="pestana">
                  Mapa de riesgo
                </Tabs.Trigger>
                <Tabs.Trigger value="distribucion" className="pestana">
                  {departamento ? 'Por provincia' : 'Por departamento'}
                </Tabs.Trigger>
              </Tabs.List>
              <InfoTip texto="Ubicación referencial de cada obra (coordenadas del cuaderno digital o de la inversión en el Banco de Inversiones). El color indica el nivel de riesgo vigente." />
            </div>
            <Tabs.Content value="mapa" className="flex-1 p-4 data-[state=inactive]:hidden">
              <Mapa departamento={departamento} />
            </Tabs.Content>
            <Tabs.Content value="distribucion" className="p-4">
              <p className="mb-2 text-[13px] text-slate-500">Obras con cuaderno digital evaluadas en el corte vigente y cuántas están en riesgo alto.</p>
              <Distribucion datos={d.distribucion} departamento={departamento} />
            </Tabs.Content>
          </Tabs.Root>
        </div>
      </div>
      <Confiabilidad historico={d.historico} />
    </div>
  )
}
