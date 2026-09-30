import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Building2, CalendarDays, ExternalLink, FileText, Highlighter, MapPin, Tag } from 'lucide-react'
import { Tabs } from 'radix-ui'
import { useMemo, useState, type ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, ESTADOS, fmtFecha, fmtMes, fmtNum, fmtPct, fmtSoles, nombreObra, qs, ROL, SECTOR, titulo, useCalibracion, type Evidencia, type Explicacion, type Factor, type Nivel, urlSegura } from '../api'
import { useAuth } from '../auth'
import { ConfianzaNivel, ListaFactores, VecesPromedio } from '../components/Factores'
import { Cargando, CargandoPagina, Dato, ErrorMsg, EscalaRiesgo, InfoTip, Migas, NivelBadge, Paginacion, Panel, Seccion, Vacio } from '../components/ui'
import { COLOR_NIVEL, COLORES, SERIE } from '../lib/colores'
import { NIVEL_TEXTO } from '../lib/nivel'
import { urlPdf } from '../estatico'

interface Detalle {
  obra: Record<string, any> // eslint-disable-line @typescript-eslint/no-explicit-any
  infobras: Record<string, any> | null // eslint-disable-line @typescript-eslint/no-explicit-any
  contraloria_paralizada: { fecha_corte: string; avance_fisico: number; causal: string }[]
  enlaces: { fuente: string; url: string }[]
}
interface Riesgo {
  predicciones: { prediccion_id: number; fecha_corte: string; tipo: string; score: number; nivel: Nivel; alerta: boolean; y_observado: number | null }[]
  actividad_mensual: { mes: string; total: number; ampliaciones: number; suspensiones: number; adicionales: number; atraso_normativo: number }[]
  eventos: { fecha: string; tipo: string; tipo_std: string; nro_asiento: number; titulo: string }[]
}
interface Asiento {
  id: number
  nro_asiento: number
  fecha: string
  rol: string
  tipo: string
  tipo_std: string
  titulo: string
  descripcion: string
  archivo_fuente: string
}

const TIPOS: Record<string, string> = {
  AMPLIACION_PLAZO: 'Ampliación de plazo',
  SUSPENSION_PLAZO: 'Suspensión del plazo',
  VALORIZACION_MENOR_80: 'Valorización menor al 80 %',
  CALENDARIO_ACELERADO: 'Calendario acelerado',
  ADICIONALES: 'Adicionales de obra',
  VALORIZACIONES: 'Valorizaciones',
  CONSULTAS: 'Consultas',
  PENALIDADES: 'Penalidades',
  ORDENES: 'Órdenes',
  OTRAS_OCURRENCIAS: 'Otras ocurrencias',
}
const HITOS_CRITICOS = ['VALORIZACION_MENOR_80', 'CALENDARIO_ACELERADO', 'RESOLUCION_CONTRATO']
const FUENTE_EVIDENCIA: Record<string, string> = {
  ASIENTO: 'Cuaderno de obra',
  SIAF: 'Ejecución del gasto (SIAF)',
  MEF_SEGUIMIENTO: 'Seguimiento Invierte.pe',
  HISTORIAL: 'Historial de obras anteriores',
  INFOBRAS: 'INFOBRAS',
}

function Meta({ icono, children }: { icono: ReactNode; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-sm text-slate-600">
      <span className="text-slate-400">{icono}</span>
      {children}
    </span>
  )
}

export default function ObraDetalle() {
  const { id = '' } = useParams()
  const d = useQuery({ queryKey: ['obra', id], queryFn: () => api<Detalle>(`/obras/${id}`) })
  const r = useQuery({ queryKey: ['riesgo', id], queryFn: () => api<Riesgo>(`/obras/${id}/riesgo`) })
  const cal = useCalibracion()
  const [sel, setSel] = useState<number | null>(null)
  const [tab, setTab] = useState('factores')
  const preds = r.data?.predicciones ?? []
  const pid = sel ?? preds.at(-1)?.prediccion_id ?? null
  const ex = useQuery({ queryKey: ['exp', pid], queryFn: () => api<Explicacion>(`/predicciones/${pid}`), enabled: pid !== null })

  if (d.isLoading) return <CargandoPagina />
  if (d.error) return <ErrorMsg error={d.error} reintentar={() => d.refetch()} />
  const o = d.data!.obra
  const vigente = o.tipo_prediccion === 'vigente' && o.score !== null
  const suben = (ex.data?.factores ?? []).filter((f) => f.shap > 0)
  return (
    <div className="space-y-5">
      <div>
        <Migas items={[{ a: '/obras', l: 'Alertas del cuaderno' }, { l: 'Ficha de la obra' }]} />
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h1 className="max-w-4xl font-display text-xl leading-snug font-semibold text-slate-900 sm:text-2xl" title={o.denominacion}>
            {nombreObra(o.denominacion)}
          </h1>
          <div className="flex flex-wrap gap-2">
            {o.score !== null && (
              <a href={urlPdf(o.cuaderno_id)} className="btn-primario">
                <FileText className="size-4" /> Informe técnico PDF
              </a>
            )}
          </div>
        </div>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1.5">
          <Meta icono={<MapPin className="size-4" />}>
            {[o.distrito, o.provincia, o.departamento].filter(Boolean).map(titulo).join(', ')}
          </Meta>
          <Meta icono={<Building2 className="size-4" />}>{o.entidad ?? 'Entidad no identificada'}</Meta>
          <Meta icono={<Tag className="size-4" />}>{SECTOR[o.sector] ?? titulo(o.sector)}</Meta>
          <Meta icono={<CalendarDays className="size-4" />}>{ESTADOS[o.estado_observado] ?? o.estado_observado}</Meta>
        </div>
      </div>

      {vigente ? (
        <section className="tarjeta overflow-hidden">
          <div className="grid gap-5 p-5 md:grid-cols-[1.1fr_0.8fr_1.4fr]">
            <div>
              <div className="flex items-center gap-1 text-sm font-medium text-slate-600">
                Riesgo de atraso formal en los próximos 60 días <InfoTip termino="atraso_formal" />
              </div>
              <div className="mt-2 flex items-baseline gap-3">
                <span className="text-3xl font-semibold tracking-tight" style={{ color: COLOR_NIVEL[o.nivel as Nivel] }}>
                  {NIVEL_TEXTO[o.nivel as Nivel]}
                </span>
                <span className="num text-lg font-medium text-slate-700">{fmtPct(o.score)}</span>
                <InfoTip termino="probabilidad" />
              </div>
              <div className="mt-1">
                <VecesPromedio score={o.score} base={cal.data?.alerta_60d.tasa_base} />
              </div>
              <div className="mt-1 text-xs text-slate-500">Corte {fmtFecha(o.fecha_corte)}</div>
            </div>
            <div>
              <div className="mb-2 text-sm font-medium text-slate-600">Posición entre las obras evaluadas</div>
              <EscalaRiesgo percentil={o.percentil} nivel={o.nivel} />
            </div>
            <div>
              <div className="mb-2 text-sm font-medium text-slate-600">Confiabilidad de este nivel</div>
              <ConfianzaNivel nivel={o.nivel} />
            </div>
          </div>
          <div className="border-t border-slate-100 bg-slate-50/70 px-5 py-4">
            <div className="text-sm font-medium text-slate-700">Principales factores que elevan el riesgo</div>
            {ex.isLoading ? (
              <Cargando filas={2} />
            ) : suben.length ? (
              <ul className="mt-1.5 grid gap-x-6 gap-y-1 text-sm text-slate-800 md:grid-cols-3">
                {suben.slice(0, 3).map((f) => (
                  <li key={f.feature} className="flex gap-2">
                    <span className="mt-2 size-1.5 shrink-0 rounded-full bg-alto" aria-hidden />
                    {f.descripcion}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-1 text-sm text-slate-500">Ningún factor eleva el riesgo por encima del promedio.</p>
            )}
            <button className="enlace mt-2 text-sm" onClick={() => setTab('factores')}>
              Ver todos los factores y la evidencia
            </button>
          </div>
        </section>
      ) : (
        <div className="tarjeta flex flex-wrap items-center gap-3 p-4 text-sm text-slate-700">
          <CalendarDays className="size-5 text-slate-400" />
          <span className="flex-1">
            Esta obra no tiene una predicción vigente
            {o.fecha_atraso ? `: ya registró el atraso formal el ${fmtFecha(o.fecha_atraso)}` : ' (culminada, con contrato resuelto o sin registros recientes)'}. Se muestra su historial para
            auditar las estimaciones pasadas.
          </span>
        </div>
      )}

      <Tabs.Root value={tab} onValueChange={setTab}>
        <Tabs.List className="pestanas" aria-label="Secciones de la ficha">
          <Tabs.Trigger value="factores" className="pestana">
            Factores y evidencia
          </Tabs.Trigger>
          <Tabs.Trigger value="evolucion" className="pestana">
            Evolución del riesgo
          </Tabs.Trigger>
          <Tabs.Trigger value="asientos" className="pestana">
            Cuaderno de obra
          </Tabs.Trigger>
          <Tabs.Trigger value="datos" className="pestana">
            Datos de la obra
          </Tabs.Trigger>
          <Tabs.Trigger value="revision" className="pestana">
            Revisión del analista
          </Tabs.Trigger>
        </Tabs.List>
        <div className="pt-4">
          <Tabs.Content value="factores">
            <FactoresEvidencia ex={ex.data} loading={ex.isLoading} error={ex.error} preds={preds} pid={pid} setSel={setSel} />
          </Tabs.Content>
          <Tabs.Content value="evolucion">
            <Evolucion r={r.data} loading={r.isLoading} fechaAtraso={o.fecha_atraso} />
          </Tabs.Content>
          <Tabs.Content value="asientos">
            <Asientos id={id} />
          </Tabs.Content>
          <Tabs.Content value="datos">
            <DatosObra d={d.data!} />
          </Tabs.Content>
          <Tabs.Content value="revision">
            {ex.data ? <Revision cuadernoId={id} fechaCorte={ex.data.prediccion.fecha_corte} /> : <Vacio titulo="Sin predicción para revisar" />}
          </Tabs.Content>
        </div>
      </Tabs.Root>
    </div>
  )
}

function FactoresEvidencia({ ex, loading, error, preds, pid, setSel }: { ex?: Explicacion; loading: boolean; error: unknown; preds: Riesgo['predicciones']; pid: number | null; setSel: (n: number) => void }) {
  const [verFactor, setVerFactor] = useState<Factor | null>(null)
  const [todo, setTodo] = useState(false)
  const porFeature = useMemo(() => {
    const m = new Map<string, Evidencia[]>()
    ex?.evidencia.forEach((e) => m.set(e.feature, [...(m.get(e.feature) ?? []), e]))
    return m
  }, [ex])
  if (loading) return <Cargando filas={6} />
  if (error) return <ErrorMsg error={error} />
  if (!ex) return <Vacio titulo="Sin predicciones para esta obra" texto="La obra no tiene historia suficiente en el cuaderno digital para ser evaluada." />
  const p = ex.prediccion
  const selector = (
    <label className="flex max-w-full min-w-0 items-center gap-2 text-sm">
      <span className="text-slate-500">Corte</span>
      <select className="entrada min-w-0 max-w-full truncate" value={pid ?? ''} onChange={(e) => setSel(Number(e.target.value))} aria-label="Corte de la predicción">
        {[...preds].reverse().map((x) => (
          <option key={x.prediccion_id} value={x.prediccion_id}>
            {fmtMes(x.fecha_corte)} · riesgo {NIVEL_TEXTO[x.nivel].toLowerCase()} ({fmtPct(x.score)}){x.tipo === 'vigente' ? ' · vigente' : ''}
          </option>
        ))}
      </select>
    </label>
  )
  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-5">
      <div className="lg:col-span-3">
        <Seccion
          titulo="¿Por qué este nivel de riesgo?"
          ayuda="factor"
          subtitulo="Datos reales de la obra que más movieron la estimación, ordenados por su peso. Indican asociación estadística, no causas comprobadas."
          accion={selector}
        >
          <div className="mb-3 flex flex-wrap items-center gap-2 text-sm text-slate-600">
            <NivelBadge nivel={p.nivel} score={p.score} />
            <span>{p.tipo === 'vigente' ? 'Predicción vigente' : 'Predicción histórica (solo con datos de esa fecha)'}</span>
            {p.y_observado !== null && (
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${p.y_observado ? 'bg-alto-suave text-alto' : 'bg-bajo-suave text-bajo'}`}>
                Resultado: {p.y_observado ? 'sí hubo atraso formal en los 60 días' : 'no hubo atraso formal en los 60 días'}
              </span>
            )}
          </div>
          <ListaFactores factores={ex.factores} alVerEvidencia={setVerFactor} conEvidencia={new Set(porFeature.keys())} />
        </Seccion>
      </div>
      <div className="space-y-5 lg:col-span-2">
        <Seccion
          titulo="Evidencia documental"
          subtitulo="Registros oficiales asociados a los factores que elevan el riesgo."
          accion={
            ex.evidencia.length > 0 && (
              <button className="btn btn-sm" onClick={() => setTodo(true)}>
                Ver toda ({fmtNum(ex.evidencia.length)})
              </button>
            )
          }
        >
          {ex.evidencia.length === 0 ? (
            <p className="text-sm text-slate-500">Esta predicción no tiene factores de aumento de riesgo con evidencia documental asociada.</p>
          ) : (
            <ul className="space-y-2">
              {[...new Map(ex.evidencia.map((e) => [e.fuente, 0])).keys()].map((fu) => (
                <li key={fu} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
                  <span>{FUENTE_EVIDENCIA[fu] ?? fu}</span>
                  <span className="num text-slate-500">{fmtNum(ex.evidencia.filter((e) => e.fuente === fu).length)} registros</span>
                </li>
              ))}
            </ul>
          )}
        </Seccion>
        <Simulador prediccionId={p.id} />
      </div>
      <Panel abierto={!!verFactor} onClose={() => setVerFactor(null)} titulo="Evidencia del factor" subtitulo={verFactor?.descripcion} ancho="max-w-2xl">
        {verFactor && <ListaEvidencia items={porFeature.get(verFactor.feature!) ?? []} />}
      </Panel>
      <Panel abierto={todo} onClose={() => setTodo(false)} titulo="Evidencia que respalda la alerta" subtitulo={`Corte ${fmtFecha(p.fecha_corte)}`} ancho="max-w-2xl">
        <div className="space-y-5">
          {ex.factores
            .filter((f) => f.shap > 0 && porFeature.has(f.feature!))
            .map((f) => (
              <div key={f.feature}>
                <div className="mb-1.5 text-sm font-medium text-slate-800">{f.descripcion}</div>
                <ListaEvidencia items={porFeature.get(f.feature!)!} />
              </div>
            ))}
        </div>
      </Panel>
    </div>
  )
}

function ListaEvidencia({ items }: { items: Evidencia[] }) {
  return (
    <ul className="space-y-2">
      {items.map((e, i) => (
        <li key={i} className="rounded-lg border border-slate-200 p-3 text-sm">
          <div className="mb-1 flex flex-wrap gap-x-2 text-xs text-slate-500">
            <span className="font-medium text-slate-700">{e.fuente === 'ASIENTO' ? `Asiento N° ${e.nro_asiento}` : (FUENTE_EVIDENCIA[e.fuente] ?? e.fuente)}</span>
            {e.tipo && <span>{e.tipo}</span>}
            {e.rol && <span>{ROL[e.rol] ?? e.rol}</span>}
            <span>{fmtFecha(e.fecha)}</span>
            {e.referencia?.startsWith('http') && (
              <a className="enlace inline-flex items-center gap-0.5" href={e.referencia} target="_blank" rel="noopener noreferrer">
                fuente <ExternalLink className="size-3" />
              </a>
            )}
          </div>
          <div className="leading-relaxed whitespace-pre-line text-slate-700">{e.extracto}</div>
          {e.archivo_fuente && <div className="mt-1 text-xs text-slate-400">Archivo oficial: {e.archivo_fuente}</div>}
        </li>
      ))}
    </ul>
  )
}

function Simulador({ prediccionId }: { prediccionId: number }) {
  const q = useQuery({
    queryKey: ['sim', prediccionId],
    queryFn: () => api<{ escenario: string; descripcion: string; score_base: number; score_escenario: number; alerta_escenario: boolean }[]>(`/predicciones/${prediccionId}/simulacion`),
  })
  if (!q.data || q.data.length === 0) return null
  return (
    <Seccion titulo="¿Qué cambiaría la estimación?" subtitulo="El modelo recalcula el riesgo cambiando una sola señal. Muestra de qué depende la estimación; no garantiza el efecto real de una acción.">
      <ul className="space-y-3">
        {q.data.map((s) => {
          const baja = s.score_escenario < s.score_base
          return (
            <li key={s.escenario} className="text-sm">
              <div className="text-slate-700">{s.descripcion}</div>
              <div className="mt-1 flex items-center gap-2">
                <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                  <div className="absolute inset-y-0 left-0 rounded-full bg-slate-300" style={{ width: `${100 * s.score_base}%` }} />
                  <div className={`absolute inset-y-0 left-0 rounded-full ${baja ? 'bg-bajo' : 'bg-alto'}`} style={{ width: `${100 * s.score_escenario}%`, opacity: 0.8 }} />
                </div>
                <span className="num w-28 shrink-0 text-right text-xs text-slate-600">
                  {fmtPct(s.score_base)} → <b className={baja ? 'text-bajo' : 'text-alto'}>{fmtPct(s.score_escenario)}</b>
                </span>
              </div>
            </li>
          )
        })}
      </ul>
    </Seccion>
  )
}

function Evolucion({ r, loading, fechaAtraso }: { r?: Riesgo; loading: boolean; fechaAtraso: string | null }) {
  const cal = useCalibracion()
  const modelo = useQuery({ queryKey: ['modelo'], queryFn: () => api<{ umbral_alerta: number }>('/modelo') })
  const serie = useMemo(() => {
    const m = new Map<string, Record<string, number | string | null>>()
    for (const a of r?.actividad_mensual ?? []) m.set(a.mes.slice(0, 7), { mes: a.mes.slice(0, 7), asientos: a.total, suspensiones: a.suspensiones, ampliaciones: a.ampliaciones })
    for (const p of r?.predicciones ?? []) {
      const k = p.fecha_corte.slice(0, 7)
      m.set(k, { ...(m.get(k) ?? { mes: k }), riesgo: Math.round(1000 * p.score) / 10 })
    }
    return [...m.values()].sort((a, b) => String(a.mes).localeCompare(String(b.mes)))
  }, [r])
  if (loading) return <Cargando filas={6} />
  const onset = fechaAtraso ? String(fechaAtraso).slice(0, 7) : null
  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
      <div className="lg:col-span-2">
        <Seccion
          titulo="Riesgo estimado mes a mes"
          subtitulo="Probabilidad de atraso formal en los 60 días siguientes, calculada cada mes solo con la información disponible en esa fecha. Debajo, la actividad registrada en el cuaderno."
        >
          <div className="h-64" role="img" aria-label="Riesgo estimado por mes">
            <ResponsiveContainer>
              <LineChart data={serie} syncId="evolucion-obra" margin={{ left: -8, right: 12, top: 10 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={COLORES.rejilla} />
                <XAxis dataKey="mes" tick={{ fontSize: 12 }} tickFormatter={(m) => fmtMes(m + '-01')} minTickGap={16} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} unit="%" width={48} />
                <Tooltip labelFormatter={(m) => fmtMes(m + '-01')} formatter={(v) => [`${v}\u00a0%`, 'Riesgo estimado']} />
                <Line isAnimationActive={false} dataKey="riesgo" name="Riesgo estimado" stroke={SERIE[0]} strokeWidth={2.5} dot={{ r: 3 }} connectNulls />
                {modelo.data && (
                  <ReferenceLine y={100 * modelo.data.umbral_alerta} stroke={COLOR_NIVEL.ALTO} strokeDasharray="5 4" label={{ value: 'umbral de riesgo alto', fontSize: 12, fill: COLOR_NIVEL.ALTO, position: 'insideTopLeft' }} />
                )}
                {onset && <ReferenceLine x={onset} stroke="#334155" strokeWidth={1.5} label={{ value: 'atraso formal registrado', fontSize: 12, fill: '#334155', position: 'insideTopRight' }} />}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 h-40" role="img" aria-label="Asientos y suspensiones registrados por mes">
            <ResponsiveContainer>
              <BarChart data={serie} syncId="evolucion-obra" margin={{ left: -8, right: 12, top: 4 }} barGap={2}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={COLORES.rejilla} />
                <XAxis dataKey="mes" tick={{ fontSize: 12 }} tickFormatter={(m) => fmtMes(m + '-01')} minTickGap={16} />
                <YAxis tick={{ fontSize: 12 }} width={48} allowDecimals={false} />
                <Tooltip labelFormatter={(m) => fmtMes(m + '-01')} />
                <Legend wrapperStyle={{ fontSize: 13 }} />
                <Bar isAnimationActive={false} dataKey="asientos" name="Asientos del mes" fill={COLORES.marcaClaro} radius={[3, 3, 0, 0]} />
                <Bar isAnimationActive={false} dataKey="suspensiones" name="Suspensiones de plazo" fill={SERIE[1]} radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          {cal.data && <p className="mt-3 text-sm text-slate-600">Referencia: la tasa promedio de atraso formal a 60 días es {fmtPct(cal.data.alerta_60d.tasa_base)}.</p>}
        </Seccion>
      </div>
      <Seccion titulo="Hitos del cuaderno">
        {(r?.eventos ?? []).length === 0 ? (
          <p className="text-sm text-slate-500">Sin hitos registrados.</p>
        ) : (
          <ol className="relative space-y-3 border-l border-slate-200 pl-4">
            {r!.eventos.map((e, i) => (
              <li key={i} className="text-sm">
                <span className={`absolute -left-[5px] mt-1.5 size-2.5 rounded-full ring-2 ring-white ${HITOS_CRITICOS.includes(e.tipo_std) ? 'bg-alto' : 'bg-slate-300'}`} />
                <div className="text-xs text-slate-500">
                  {fmtFecha(e.fecha)} · asiento N° {e.nro_asiento}
                </div>
                <div className={HITOS_CRITICOS.includes(e.tipo_std) ? 'font-medium text-alto' : 'text-slate-700'}>{e.tipo}</div>
              </li>
            ))}
          </ol>
        )}
      </Seccion>
    </div>
  )
}

function DatosObra({ d }: { d: Detalle }) {
  const o = d.obra
  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
      <Seccion titulo="Datos integrados de la obra" className="lg:col-span-2">
        <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div className="sm:col-span-2 lg:col-span-3">
            <Dato l="Denominación oficial (tal como la publica OECE)" v={o.denominacion} />
          </div>
          <Dato l="Entidad contratante" v={o.entidad} />
          <Dato l="Contratista" v={o.contratista} />
          <Dato l="Código Único de Inversión" ayuda="cui" v={o.cui ? `${o.cui}${o.cui_metodo_enlace === 'fuzzy_tfidf' ? ' (identificado por similitud del nombre)' : ''}` : 'No enlazado'} />
          <Dato l="Función y nivel de gobierno" v={o.funcion ? `${titulo(o.funcion)} · ${o.nivel_gobierno ?? '—'}` : null} />
          <Dato l="Monto aprobado de la inversión" v={fmtSoles(o.monto_viable)} />
          <Dato l="Monto del contrato" v={fmtSoles(o.monto_contrato)} />
          <Dato l="Plazo original" v={o.plazo_original_dias ? `${fmtNum(o.plazo_original_dias)} días` : null} />
          <Dato l="Asientos registrados" ayuda="cuaderno" v={`${fmtNum(o.n_asientos)} (${fmtFecha(o.primer_asiento)} – ${fmtFecha(o.ultimo_asiento)})`} />
          <Dato l="Estado observado" v={ESTADOS[o.estado_observado] ?? o.estado_observado} />
        </dl>
        {d.infobras && (
          <div className="mt-5 rounded-lg bg-slate-50 p-3 text-sm text-slate-600">
            <b className="text-slate-700">INFOBRAS</b> (registro al {fmtFecha(d.infobras.fecha_consulta)}): {d.infobras.estado_ejecucion}; avance físico real {fmtNum(d.infobras.avance_fisico_real, 1)} % frente a{' '}
            {fmtNum(d.infobras.avance_fisico_programado, 1)} % programado. Es un dato informativo: no se usa para predecir porque INFOBRAS solo publica la situación actual.
          </div>
        )}
        {d.contraloria_paralizada.length > 0 && (
          <div className="mt-3 rounded-lg border border-red-200 bg-alto-suave p-3 text-sm text-red-900">
            Figura en {d.contraloria_paralizada.length} {d.contraloria_paralizada.length === 1 ? 'reporte' : 'reportes'} de obras paralizadas de la Contraloría (último:{' '}
            {fmtFecha(d.contraloria_paralizada.at(-1)!.fecha_corte)}; causa registrada: {d.contraloria_paralizada.at(-1)!.causal}).
          </div>
        )}
      </Seccion>
      <Seccion titulo="Fuentes oficiales" subtitulo="Consulte los registros originales en los portales del Estado.">
        {d.enlaces.length === 0 ? (
          <p className="text-sm text-slate-500">La obra no tiene enlaces a otras fuentes.</p>
        ) : (
          <ul className="space-y-2">
            {d.enlaces.filter((e) => urlSegura(e.url)).map((e) => (
              <li key={e.url}>
                <a href={urlSegura(e.url)!} target="_blank" rel="noopener noreferrer" className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:border-marca-200 hover:bg-marca-50">
                  {e.fuente}
                  <ExternalLink className="size-4 text-slate-400" />
                </a>
              </li>
            ))}
          </ul>
        )}
      </Seccion>
    </div>
  )
}

function Revision({ cuadernoId, fechaCorte }: { cuadernoId: string; fechaCorte: string }) {
  const { usuario } = useAuth()
  const qc = useQueryClient()
  const [decision, setDecision] = useState('EN_SEGUIMIENTO')
  const [comentario, setComentario] = useState('')
  const key = ['rev', cuadernoId, fechaCorte]
  const q = useQuery({
    queryKey: key,
    queryFn: () => api<{ id: number; decision: string; comentario: string; creado_en: string; usuario: string }[]>(`/alertas/${cuadernoId}/${fechaCorte}/revisiones`),
    enabled: !!usuario,
  })
  const m = useMutation({
    mutationFn: () => api(`/alertas/${cuadernoId}/${fechaCorte}/revisiones`, { method: 'POST', body: JSON.stringify({ decision, comentario: comentario || null }) }),
    onSuccess: () => {
      setComentario('')
      qc.invalidateQueries({ queryKey: key })
    },
  })
  const DEC: Record<string, string> = { EN_SEGUIMIENTO: 'En seguimiento', CONFIRMADA: 'Confirmada en campo', DESCARTADA: 'Descartada' }
  if (!usuario)
    return (
      <div className="tarjeta">
        <Vacio
          titulo="Ingrese como analista para registrar una revisión"
          texto="La consulta es pública; registrar si una alerta fue confirmada o descartada requiere una cuenta de analista y queda en el registro de auditoría."
          accion={
            <Link to="/login" className="btn-primario">
              Ingresar
            </Link>
          }
        />
      </div>
    )
  return (
    <Seccion titulo={`Revisión de la alerta del ${fmtFecha(fechaCorte)}`} subtitulo="Cada registro queda en la bitácora de auditoría con su autor y fecha.">
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          m.mutate()
        }}
      >
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">
          Decisión
          <select className="entrada" value={decision} onChange={(e) => setDecision(e.target.value)}>
            {Object.entries(DEC).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </label>
        <label className="flex min-w-60 flex-1 flex-col gap-1 text-xs font-medium text-slate-500">
          Comentario (opcional)
          <input className="entrada" maxLength={2000} value={comentario} onChange={(e) => setComentario(e.target.value)} />
        </label>
        <button className="btn-primario" disabled={m.isPending}>
          {m.isPending ? 'Registrando…' : 'Registrar revisión'}
        </button>
      </form>
      {m.error && <p className="mt-2 text-sm text-red-700">{(m.error as Error).message}</p>}
      {m.isSuccess && <p className="mt-2 text-sm text-bajo">Revisión registrada.</p>}
      <ul className="mt-4 divide-y divide-slate-100 text-sm">
        {(q.data ?? []).map((x) => (
          <li key={x.id} className="py-2">
            <b>{DEC[x.decision] ?? x.decision}</b> · {x.usuario} · {fmtFecha(x.creado_en)}
            {x.comentario && <div className="text-slate-600">{x.comentario}</div>}
          </li>
        ))}
      </ul>
    </Seccion>
  )
}

const CRITICOS: [RegExp, string][] = [
  [/(falta de personal|ausencia del (residente|especialista|ingeniero)|personal insuficiente|no se encuentra (el )?(residente|especialista))/gi, 'bg-red-100'],
  [/(maquinaria|equipo (inoperativo|malogrado|averiado)|falla mec[aá]nica)/gi, 'bg-orange-100'],
  [/(incompatibilidad|deficiencias? (del|en el) expediente|error(es)? en (el )?expediente|vicios ocultos)/gi, 'bg-purple-100'],
  [/(falta de pago|pago pendiente|adelanto|desabastec|falta de material)/gi, 'bg-yellow-100'],
  [/(paraliz|atras|retras|demora|incumpl|penalidad)/gi, 'bg-rose-100'],
  [/(lluvia|precipitaci)/gi, 'bg-sky-100'],
]

function Resaltado({ texto, activo }: { texto: string; activo: boolean }) {
  if (!activo || !texto) return <>{texto}</>
  const marcas: { i: number; f: number; c: string }[] = []
  for (const [rx, c] of CRITICOS) for (const m of texto.matchAll(rx)) marcas.push({ i: m.index!, f: m.index! + m[0].length, c })
  marcas.sort((a, b) => a.i - b.i)
  const out: ReactNode[] = []
  let pos = 0
  marcas.forEach((m, k) => {
    if (m.i < pos) return
    out.push(texto.slice(pos, m.i))
    out.push(
      <mark key={k} className={`${m.c} rounded px-0.5 text-inherit`}>
        {texto.slice(m.i, m.f)}
      </mark>,
    )
    pos = m.f
  })
  out.push(texto.slice(pos))
  return <>{out}</>
}

function Asientos({ id }: { id: string }) {
  const [pagina, setPagina] = useState(1)
  const [tipo, setTipo] = useState('')
  const [q, setQ] = useState('')
  const [buscar, setBuscar] = useState('')
  const [abierto, setAbierto] = useState<number | null>(null)
  const [resaltar, setResaltar] = useState(false)
  const r = useQuery({
    queryKey: ['asientos', id, tipo, buscar, pagina],
    queryFn: () => api<{ total: number; items: Asiento[] }>(`/obras/${id}/asientos${qs({ tipo, q: buscar, pagina, tamanio: 15 })}`),
    placeholderData: (p) => p,
  })
  return (
    <section className="tarjeta overflow-hidden">
      <form
        className="flex flex-wrap items-end gap-2 border-b border-slate-100 p-3"
        onSubmit={(e) => {
          e.preventDefault()
          setBuscar(q)
          setPagina(1)
        }}
      >
        <input className="entrada min-w-0 flex-1 sm:min-w-56" aria-label="Buscar en los asientos" placeholder="Buscar en el texto (p. ej.: lluvias, falta de pago, expediente)" value={q} maxLength={200} onChange={(e) => setQ(e.target.value)} />
        <select
          aria-label="Tipo de asiento"
          className="entrada"
          value={tipo}
          onChange={(e) => {
            setTipo(e.target.value)
            setPagina(1)
          }}
        >
          <option value="">Todos los tipos</option>
          {Object.entries(TIPOS).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <button className="btn" type="submit">
          Buscar
        </button>
        <label className="ml-auto inline-flex items-center gap-2 text-sm text-slate-600">
          <input type="checkbox" checked={resaltar} onChange={(e) => setResaltar(e.target.checked)} className="accent-marca-600" />
          <Highlighter className="size-4" /> Resaltar palabras clave
          <InfoTip texto="Marca menciones de personal, maquinaria, expediente técnico, pagos y materiales, atrasos e incumplimientos, y lluvias. Es una búsqueda por palabras, no una predicción." />
        </label>
      </form>
      {r.isLoading ? (
        <div className="p-4">
          <Cargando filas={6} />
        </div>
      ) : r.error ? (
        <div className="p-4">
          <ErrorMsg error={r.error} />
        </div>
      ) : r.data!.items.length === 0 ? (
        <Vacio titulo="No hay asientos con esos criterios" />
      ) : (
        <>
          <ul className={`divide-y divide-slate-100 ${r.isFetching ? 'opacity-60' : ''}`}>
            {r.data!.items.map((a) => (
              <li key={a.id} className="px-4 py-3">
                <button className="w-full text-left" onClick={() => setAbierto(abierto === a.id ? null : a.id)} aria-expanded={abierto === a.id}>
                  <div className="flex flex-wrap gap-x-2 text-xs text-slate-500">
                    <span className="num">{fmtFecha(a.fecha)}</span>
                    <span>N° {a.nro_asiento}</span>
                    <span>{a.tipo}</span>
                    <span>{ROL[a.rol] ?? a.rol}</span>
                  </div>
                  <div className="mt-0.5 text-sm font-medium text-slate-900">{a.titulo}</div>
                </button>
                <div className={`mt-1 text-sm leading-relaxed whitespace-pre-line text-slate-700 ${abierto === a.id || resaltar ? '' : 'line-clamp-2'}`}>
                  <Resaltado texto={a.descripcion} activo={resaltar} />
                </div>
              </li>
            ))}
          </ul>
          <Paginacion pagina={pagina} total={r.data!.total} tamanio={15} onChange={setPagina} />
        </>
      )}
    </section>
  )
}
