import { useQuery } from '@tanstack/react-query'
import { CheckCircle2, Crosshair, Gauge, Scale } from 'lucide-react'
import { Tabs } from 'radix-ui'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, fmtDec, fmtFecha, fmtMes, fmtNum, fmtPct, qs, titulo, useCalibracion, type Nivel } from '../api'
import { useAmbito } from '../ambito'
import { useFiltrosUrl } from '../lib/filtrosUrl'
import { BarraProporcion, Cargando, CargandoPagina, EncabezadoPagina, ErrorMsg, InfoTip, NivelBadge, Paginacion, Seccion, Segmentado, Vacio } from '../components/ui'
import { COLORES, SERIE } from '../lib/colores'
import { DetalleTecnico, TablaPoliticas, type Modelo } from './Modelo'
import { NIVEL_TEXTO } from '../lib/nivel'

interface CardCartera {
  umbrales: Record<string, { alto: number; medio: number; tasa_base_test: number; periodo_test_desde: string; tasa_por_nivel_test: Record<string, { filas: number; tasa_retraso_observada: number }> }>
  metricas_test: Record<string, Record<string, { arequipa: Record<string, number>; nacional: Record<string, number> }>>
  periodos: Record<string, Record<string, (string | number)[]>>
}

function Respuesta({ icono, pregunta, respuesta, dato, ayuda }: { icono: ReactNode; pregunta: string; respuesta: ReactNode; dato: ReactNode; ayuda?: 'roc_auc' | 'calibracion' | 'backtest' }) {
  return (
    <div className="tarjeta flex flex-col p-4">
      <div className="flex items-center gap-2 text-sm font-medium text-slate-600">
        <span className="flex size-7 items-center justify-center rounded-lg bg-marca-50 text-marca-600">{icono}</span>
        {pregunta}
        {ayuda && <InfoTip termino={ayuda} />}
      </div>
      <div className="num mt-3 text-2xl font-semibold tracking-tight text-slate-900">{dato}</div>
      <p className="mt-1 text-sm leading-relaxed text-slate-600">{respuesta}</p>
    </div>
  )
}

function Calibracion() {
  const c = useCalibracion()
  if (c.isLoading) return <Cargando />
  if (c.error || !c.data) return <ErrorMsg error={c.error ?? 'Sin datos'} />
  const d = c.data.alerta_60d.deciles.map((x) => ({ decil: `${x.decil}`, estimada: +(100 * x.probabilidad_media).toFixed(1), observada: +(100 * x.tasa_observada).toFixed(1) }))
  return (
    <Seccion
      titulo="¿Las probabilidades coinciden con lo que ocurrió?"
      ayuda="calibracion"
      subtitulo={`Obras-mes agrupadas en 10 grupos de igual tamaño según su probabilidad estimada (1 = menor riesgo). Validación con datos pasados de ${fmtMes(c.data.alerta_60d.desde)} a ${fmtMes(c.data.alerta_60d.hasta)}.`}
    >
      <div className="h-72">
        <ResponsiveContainer>
          <ComposedChart data={d} margin={{ left: -14, right: 8, top: 8, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={COLORES.rejilla} />
            <XAxis dataKey="decil" tick={{ fontSize: 11 }} label={{ value: 'Grupo de riesgo (decil)', position: 'insideBottom', offset: -6, fontSize: 11, fill: '#64748b' }} height={40} />
            <YAxis unit="%" tick={{ fontSize: 11 }} />
            <Tooltip formatter={(v) => `${v} %`} labelFormatter={(l) => `Grupo ${l}`} />
            <Legend wrapperStyle={{ fontSize: 12 }} verticalAlign="top" />
            <Bar isAnimationActive={false} dataKey="observada" name="Atraso formal observado" fill={SERIE[0]} radius={[3, 3, 0, 0]} />
            <Line isAnimationActive={false} dataKey="estimada" name="Probabilidad estimada (promedio)" stroke={SERIE[1]} strokeWidth={2} dot={{ r: 3 }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-sm text-slate-600">Si las barras y la línea coinciden, las probabilidades pueden leerse literalmente: de 100 obras con 20 % estimado, alrededor de 20 tuvieron el atraso formal.</p>
    </Seccion>
  )
}

function Niveles() {
  const c = useCalibracion()
  if (!c.data) return null
  const max = Math.max(...c.data.alerta_60d.niveles.map((n) => n.tasa_observada))
  return (
    <Seccion titulo="Resultado real de cada nivel de riesgo" ayuda="confiabilidad" subtitulo="Proporción de obras de cada nivel que registró el atraso formal en los 60 días siguientes.">
      <ul className="space-y-4">
        {c.data.alerta_60d.niveles.map((n) => (
          <li key={n.nivel}>
            <div className="mb-1 flex items-center justify-between text-sm">
              <NivelBadge nivel={n.nivel} compacto />
              <span className="num text-slate-600">
                <b className="text-slate-900">{fmtPct(n.tasa_observada, 1)}</b> de {fmtNum(n.n)} obras-mes
              </span>
            </div>
            <BarraProporcion valor={n.tasa_observada} max={max} tono={n.nivel === 'ALTO' ? 'alto' : n.nivel === 'MEDIO' ? 'medio' : 'bajo'} />
          </li>
        ))}
      </ul>
      <p className="mt-4 text-sm text-slate-600">Promedio general: {fmtPct(c.data.alerta_60d.tasa_base, 1)}. Una alerta de nivel alto no es una certeza: indica dónde es más probable encontrar el problema.</p>
    </Seccion>
  )
}

function Alerta60({ md }: { md: Modelo }) {
  const bn = md.metricas.operacion_backtest_nacional
  const ba = md.metricas.operacion_backtest_arequipa
  const ma = md.metricas.arequipa
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <Calibracion />
        </div>
        <div className="lg:col-span-2">
          <Niveles />
        </div>
      </div>
      {bn && (
        <Seccion
          titulo="¿Cuánto rinde revisar según el riesgo?"
          ayuda="backtest"
          subtitulo="Cada mes del periodo de prueba se aplicó el modelo reentrenado solo con datos anteriores, se eligieron obras para revisar con distintas estrategias y se contrastó con lo ocurrido."
        >
          <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            <TablaPoliticas titulo="Todo el Perú" b={bn} />
            {ba && <TablaPoliticas titulo="Arequipa" b={ba} />}
          </div>
        </Seccion>
      )}
      <Seccion titulo="Anticipación en Arequipa" subtitulo="Obras de la prueba que registraron el atraso formal y fueron alertadas antes de que ocurriera.">
        <p className="text-sm text-slate-700">
          <b className="num">{fmtNum(ma.obras_alertadas_antes_del_onset)}</b> de <b className="num">{fmtNum(ma.obras_con_onset_en_test)}</b> obras fueron alertadas antes del evento, con una mediana de{' '}
          <b className="num">{fmtNum(ma.anticipacion_mediana_dias, 1)}</b> días de anticipación.
        </p>
      </Seccion>
    </div>
  )
}

function ModelosCartera() {
  const q = useQuery({ queryKey: ['modelo-cartera'], queryFn: () => api<CardCartera>('/modelo/cartera') })
  if (q.isLoading) return <Cargando />
  if (q.error || !q.data) return <ErrorMsg error={q.error ?? 'Sin datos'} />
  const c = q.data
  return (
    <div className="space-y-5">
      <Seccion titulo="Qué se predice" ayuda="retraso_significativo">
        <p className="text-sm leading-relaxed text-slate-700">
          Si la obra terminará después de su fecha programada original más un 30 % de su plazo. El resultado solo se asigna con evidencia (fecha real de fin o registros posteriores al límite). El
          modelo <b>al inicio</b> usa solo lo conocido al empezar la obra, incluido el historial de la entidad, el ejecutor y la provincia. El modelo <b>de seguimiento</b> añade cada mes el avance
          del plazo y la ejecución del gasto (SIAF, con un mes de rezago).
        </p>
      </Seccion>
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {(['inicio', 'seguimiento'] as const).map((t) => {
          const m = t === 'inicio' ? c.metricas_test.inicio.lgbm : c.metricas_test.seguimiento.seguimiento_lgbm
          const base = t === 'seguimiento' ? c.metricas_test.seguimiento.exante_lgbm : c.metricas_test.inicio.regla
          const u = c.umbrales[t]
          const per = c.periodos[t]
          const max = Math.max(...(['ALTO', 'MEDIO', 'BAJO'] as Nivel[]).map((n) => u.tasa_por_nivel_test[n]?.tasa_retraso_observada ?? 0))
          return (
            <Seccion
              key={t}
              titulo={t === 'inicio' ? 'Estimación al inicio de la obra' : 'Seguimiento mensual con el gasto'}
              subtitulo={`Prueba temporal: ${per.test?.[0]} a ${per.test?.[1]} (${fmtNum(Number(per.test?.[2]))} ${t === 'inicio' ? 'obras' : 'obras-mes'}).`}
            >
              <dl className="grid grid-cols-2 gap-3 text-sm">
                <div className="rounded-lg bg-slate-50 p-3">
                  <dt className="flex items-center gap-1 text-xs text-slate-500">
                    ROC-AUC nacional <InfoTip termino="roc_auc" />
                  </dt>
                  <dd className="num mt-1 text-xl font-semibold">{fmtDec(m.nacional.roc_auc, 3)}</dd>
                  <dd className="text-xs text-slate-500">
                    {t === 'inicio' ? 'Regla del historial de la entidad' : 'Solo estimación al inicio'}: {fmtDec(base.nacional.roc_auc, 3)}
                  </dd>
                </div>
                <div className="rounded-lg bg-slate-50 p-3">
                  <dt className="flex items-center gap-1 text-xs text-slate-500">
                    PR-AUC nacional <InfoTip termino="pr_auc" />
                  </dt>
                  <dd className="num mt-1 text-xl font-semibold">{fmtDec(m.nacional.pr_auc, 3)}</dd>
                  <dd className="text-xs text-slate-500">Azar: {fmtDec(m.nacional.prevalencia, 3)}</dd>
                </div>
              </dl>
              <div className="mt-4 text-sm font-medium text-slate-700">Resultado real por nivel</div>
              <ul className="mt-2 space-y-3">
                {(['ALTO', 'MEDIO', 'BAJO'] as Nivel[]).map((n) => (
                  <li key={n}>
                    <div className="mb-1 flex items-center justify-between text-sm">
                      <NivelBadge nivel={n} compacto />
                      <span className="num text-slate-600">
                        <b className="text-slate-900">{fmtPct(u.tasa_por_nivel_test[n]?.tasa_retraso_observada)}</b> terminó con retraso ({fmtNum(u.tasa_por_nivel_test[n]?.filas)})
                      </span>
                    </div>
                    <BarraProporcion valor={u.tasa_por_nivel_test[n]?.tasa_retraso_observada ?? 0} max={max} tono={n === 'ALTO' ? 'alto' : n === 'MEDIO' ? 'medio' : 'bajo'} />
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-xs text-slate-500">
                Promedio: {fmtPct(u.tasa_base_test)}. Niveles fijados con predicciones anteriores al {fmtFecha(u.periodo_test_desde)} (alto = 20 % de mayor riesgo; medio = siguiente 30 %).
              </p>
            </Seccion>
          )
        })}
      </div>
    </div>
  )
}

interface FilaSector {
  sector: string
  filas: number
  obras: number
  positivos: number
  prevalencia: number
  roc_auc: number
  pr_auc: number
  lift_top10: number
  roc_ic95: [number, number]
}
interface BloqueSector {
  modelo: string
  global: Omit<FilaSector, 'sector'>
  sectores: FilaSector[]
}
const NOMBRE_SECTOR: Record<string, string> = { SIN_CUI: 'Sin inversión enlazada', OTROS: 'Otros sectores' }

function TablaSectores({ titulo: t, texto, b }: { titulo: string; texto: string; b: BloqueSector }) {
  return (
    <Seccion titulo={t} subtitulo={texto} sinRelleno ayuda="roc_auc">
      <div className="overflow-x-auto">
        <table className="tabla min-w-[760px]">
          <thead>
            <tr>
              <th>Sector o tipo de obra</th>
              <th className="text-right">Observaciones</th>
              <th className="text-right">Con el evento</th>
              <th>ROC-AUC (IC 95 %)</th>
              <th className="text-right">Concentración en el 10 % superior</th>
            </tr>
          </thead>
          <tbody>
            {[{ sector: 'Todos los sectores', ...b.global }, ...b.sectores].map((x, i) => (
              <tr key={x.sector} className={i === 0 ? 'bg-slate-50 font-medium' : ''}>
                <td>{NOMBRE_SECTOR[x.sector] ?? titulo(x.sector)}</td>
                <td className="num text-right">{fmtNum(x.filas)}</td>
                <td className="num text-right">
                  {fmtNum(x.positivos)} <span className="text-xs text-slate-500">({fmtPct(x.prevalencia)})</span>
                </td>
                <td className="min-w-56">
                  <div className="flex items-center gap-2">
                    <span className="num w-11 shrink-0">{fmtDec(x.roc_auc, 3)}</span>
                    <span className="relative h-1.5 flex-1 rounded-full bg-slate-100">
                      <span className="absolute inset-y-0 rounded-full bg-marca-200" style={{ left: `${(100 * (x.roc_ic95[0] - 0.5)) / 0.5}%`, right: `${100 - (100 * (x.roc_ic95[1] - 0.5)) / 0.5}%` }} />
                      <span className="absolute top-1/2 size-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-marca-700" style={{ left: `${(100 * (x.roc_auc - 0.5)) / 0.5}%` }} />
                    </span>
                    <span className="num shrink-0 text-xs text-slate-500">
                      [{fmtDec(x.roc_ic95[0], 3)}; {fmtDec(x.roc_ic95[1], 3)}]
                    </span>
                  </div>
                </td>
                <td className="num text-right">{fmtDec(x.lift_top10, 1)} veces el promedio</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Seccion>
  )
}

function Sectores() {
  const q = useQuery({ queryKey: ['sectores'], queryFn: () => api<Record<string, BloqueSector> | null>('/investigacion/sectores') })
  if (q.isLoading) return <Cargando />
  if (q.error) return <ErrorMsg error={q.error} />
  if (!q.data) return <Vacio titulo="Evaluación por sector no disponible" texto="Se genera al cargar la base de datos (python -m sato.pipeline load)." />
  const d = q.data
  return (
    <div className="space-y-5">
      <p className="max-w-4xl text-sm leading-relaxed text-slate-600">
        ¿Funciona igual en todos los sectores? Cada modelo se evaluó, sin reentrenarlo, sobre su periodo de prueba separando las obras por sector. Se muestran los grupos con al menos 30 obras con y sin
        el evento. La escala del ROC-AUC va de 0.5 (azar) a 1 (orden perfecto); la barra clara es el intervalo de confianza. «Concentración» indica cuántas veces más casos hay en el 10 % de obras
        con mayor riesgo que en una selección al azar.
      </p>
      <TablaSectores titulo="Alerta a 60 días (cuaderno de obra digital)" texto="Atraso formal en los 60 días siguientes; prueba de diciembre de 2025 a junio de 2026." b={d.alerta_60d} />
      <TablaSectores titulo="Cartera INFOBRAS: seguimiento mensual con el gasto" texto="Retraso significativo al término; cortes mensuales de 2024 y 2025, todas las modalidades." b={d.cartera_seguimiento} />
      <TablaSectores titulo="Cartera INFOBRAS: estimación al inicio" texto="Retraso significativo al término; obras iniciadas entre enero de 2022 y junio de 2024." b={d.cartera_inicio} />
    </div>
  )
}

interface Hist {
  codigo_infobras: string
  nombre: string
  departamento: string
  provincia: string
  fecha_inicio: string
  sobreplazo: number | null
  retraso_significativo: number | null
  score: number | null
  nivel: Nivel | null
}

function Historicas() {
  const { departamento } = useAmbito()
  const { valores, pagina, set } = useFiltrosUrl({ tab: 'alerta', hist: 'FINALIZADA' })
  const p = { departamento, estado: valores.hist, pagina, tamanio: 20, orden: 'reciente' }
  const q = useQuery({ queryKey: ['hist', p], queryFn: () => api<{ total: number; items: Hist[] }>(`/cartera${qs(p)}`), placeholderData: (x) => x })
  return (
    <Seccion
      titulo="Estimado frente a lo ocurrido, obra por obra"
      subtitulo="Cartera INFOBRAS. La estimación se calculó solo con información anterior al inicio de cada obra; permite auditar aciertos y errores."
      sinRelleno
      accion={
        <Segmentado
          etiqueta="Obras"
          valor={valores.hist}
          onChange={(v) => set({ hist: v })}
          opciones={[
            { v: 'FINALIZADA', l: 'Finalizadas' },
            { v: 'CONSUMADO', l: 'Con retraso ya consumado' },
          ]}
        />
      }
    >
      {q.isLoading ? (
        <div className="p-4">
          <Cargando />
        </div>
      ) : q.error ? (
        <div className="p-4">
          <ErrorMsg error={q.error} />
        </div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="tabla min-w-[720px]">
              <thead>
                <tr>
                  <th>Obra</th>
                  <th>Inicio</th>
                  <th>Estimación al inicio</th>
                  <th>Resultado observado</th>
                </tr>
              </thead>
              <tbody>
                {q.data!.items.map((o) => (
                  <tr key={o.codigo_infobras}>
                    <td className="max-w-xl">
                      <Link to={`/cartera/${o.codigo_infobras}`} className="line-clamp-2 font-medium text-slate-900 hover:text-marca-700 hover:underline">
                        {o.nombre}
                      </Link>
                      <div className="text-xs text-slate-500">
                        {titulo(o.provincia)}, {titulo(o.departamento)}
                      </div>
                    </td>
                    <td className="num text-sm whitespace-nowrap">{fmtFecha(o.fecha_inicio)}</td>
                    <td>
                      <NivelBadge nivel={o.nivel} score={o.score} compacto />
                    </td>
                    <td className="text-sm">
                      {o.retraso_significativo === null ? (
                        '—'
                      ) : o.retraso_significativo ? (
                        <span className="font-medium text-alto">Con retraso significativo</span>
                      ) : (
                        <span className="text-bajo">Sin retraso significativo</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Paginacion pagina={pagina} total={q.data!.total} tamanio={20} onChange={(n) => set({ pagina: n })} />
        </>
      )}
    </Seccion>
  )
}

export default function Laboratorio() {
  const m = useQuery({ queryKey: ['modelo'], queryFn: () => api<Modelo>('/modelo') })
  const cal = useCalibracion()
  const { valores, set } = useFiltrosUrl({ tab: 'alerta', hist: 'FINALIZADA' })
  if (m.isLoading || cal.isLoading) return <CargandoPagina />
  if (m.error) return <ErrorMsg error={m.error} reintentar={() => m.refetch()} />
  const md = m.data!
  const mn = md.metricas.nacional
  const top10 = md.metricas.operacion_backtest_nacional?.top_10
  const dec10 = cal.data?.alerta_60d.deciles.at(-1)
  return (
    <div className="space-y-5">
      <EncabezadoPagina
        titulo="Validación del modelo"
        descripcion="Evidencia de que las predicciones funcionan: el modelo se entrenó con el pasado y se evaluó en meses posteriores que no conoció, comparando lo estimado con lo que realmente ocurrió."
      />
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <Respuesta
          icono={<Scale className="size-4" />}
          pregunta="¿Distingue las obras que se atrasan?"
          ayuda="roc_auc"
          dato={`${Math.round(100 * mn.roc_auc)} de 100`}
          respuesta={`Al comparar una obra que tuvo atraso formal con otra que no, el modelo asignó más riesgo a la primera en ${Math.round(100 * mn.roc_auc)} de cada 100 pares (ROC-AUC ${fmtDec(mn.roc_auc, 3)}; el azar sería 50).`}
        />
        <Respuesta
          icono={<Gauge className="size-4" />}
          pregunta="¿Son realistas las probabilidades?"
          ayuda="calibracion"
          dato={dec10 ? `${fmtPct(dec10.probabilidad_media)} → ${fmtPct(dec10.tasa_observada)}` : '—'}
          respuesta={
            dec10
              ? `En el 10 % de obras con mayor riesgo, la probabilidad estimada promedio fue ${fmtPct(dec10.probabilidad_media)} y el atraso ocurrió en el ${fmtPct(dec10.tasa_observada)}. Las probabilidades están calibradas.`
              : 'Sin datos de calibración.'
          }
        />
        <Respuesta
          icono={<Crosshair className="size-4" />}
          pregunta="¿Sirve para priorizar la supervisión?"
          ayuda="backtest"
          dato={top10 ? `${fmtPct(top10.recall)} de los atrasos` : '—'}
          respuesta={
            top10
              ? `Revisando cada mes solo el 10 % de obras con mayor riesgo se habría encontrado el ${fmtPct(top10.recall)} de los atrasos formales, con ${fmtPct(top10.precision, 1)} de aciertos frente a ${fmtPct(md.metricas.operacion_backtest_nacional!.prevalencia, 1)} al azar.`
              : 'Sin datos de backtest.'
          }
        />
      </div>
      <div className="flex items-start gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
        <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-bajo" />
        <p>
          Todas las cifras se calculan con datos reales y se leen de los artefactos de evaluación del modelo vigente (versión {md.version}, algoritmo {md.algoritmo.split(' (')[0]}, horizonte de {md.horizonte_dias} días). Ninguna se ajustó
          después de ver la prueba: los umbrales se eligieron en validación.
        </p>
      </div>
      <Tabs.Root value={valores.tab} onValueChange={(v) => set({ tab: v, hist: null })}>
        <Tabs.List className="pestanas" aria-label="Secciones de la validación">
          <Tabs.Trigger value="alerta" className="pestana">
            Alerta a 60 días
          </Tabs.Trigger>
          <Tabs.Trigger value="cartera" className="pestana">
            Cartera INFOBRAS
          </Tabs.Trigger>
          <Tabs.Trigger value="sectores" className="pestana">
            Por sector
          </Tabs.Trigger>
          <Tabs.Trigger value="obras" className="pestana">
            Obra por obra
          </Tabs.Trigger>
          <Tabs.Trigger value="tecnico" className="pestana">
            Detalle técnico
          </Tabs.Trigger>
        </Tabs.List>
        <div className="pt-4">
          <Tabs.Content value="alerta">
            <Alerta60 md={md} />
          </Tabs.Content>
          <Tabs.Content value="cartera">
            <ModelosCartera />
          </Tabs.Content>
          <Tabs.Content value="sectores">
            <Sectores />
          </Tabs.Content>
          <Tabs.Content value="obras">
            <Historicas />
          </Tabs.Content>
          <Tabs.Content value="tecnico">
            <DetalleTecnico />
          </Tabs.Content>
        </div>
      </Tabs.Root>
      <p className="text-xs text-slate-500">Nivel de riesgo alto del modelo de alerta: probabilidad de {fmtPct(md.umbral_alerta, 1)} o más (umbral que maximiza F1 en validación). {NIVEL_TEXTO.MEDIO}: desde {fmtPct(md.metricas.umbral_vigilancia, 1)}.</p>
    </div>
  )
}
