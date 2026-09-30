import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Building2, CalendarDays, ExternalLink, FileText, MapPin, Tag } from 'lucide-react'
import { Tabs } from 'radix-ui'
import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Bar, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, ESTADO_OP, fmtFecha, fmtMes, fmtMillones, fmtNum, fmtPct, titulo, type Factor, type Nivel, urlSegura } from '../api'
import { ListaFactores, VecesPromedio } from '../components/Factores'
import { CargandoPagina, Dato, ErrorMsg, InfoTip, Seccion, Vacio } from '../components/ui'
import { COLOR_NIVEL, COLORES } from '../lib/colores'
import { NIVEL_TEXTO } from '../lib/nivel'

interface Riesgo {
  riesgo_id: number
  tipo: 'inicio' | 'seguimiento'
  fecha_corte: string
  score: number
  nivel: Nivel
  y_observado: number | null
  modelo_origen: string
}
interface Umbral {
  alto: number
  medio: number
  tasa_base_test: number
  periodo_test_desde: string
  tasa_por_nivel_test: Record<string, { filas: number; tasa_retraso_observada: number }>
}
interface Detalle {
  obra: Record<string, any> // eslint-disable-line @typescript-eslint/no-explicit-any
  riesgos: Riesgo[]
  explicaciones: Record<string, Factor[]>
  siaf_mensual: { mes: string; devengado: number }[]
  contraloria_paralizada: { fecha_corte: string; avance_fisico: number; causal: string }[]
  enlaces: { fuente: string; url: string }[]
  umbrales: Record<string, Umbral> | null
}

function Meta({ icono, children }: { icono: ReactNode; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[13px] text-slate-600">
      <span className="text-slate-400">{icono}</span>
      {children}
    </span>
  )
}

export default function CarteraDetalle() {
  const { codigo = '' } = useParams()
  const q = useQuery({ queryKey: ['cartera', codigo], queryFn: () => api<Detalle>(`/cartera/${codigo}`) })
  if (q.isLoading) return <CargandoPagina />
  if (q.error) return <ErrorMsg error={q.error} reintentar={() => q.refetch()} />
  const d = q.data!
  const o = d.obra
  const ini = d.riesgos.filter((r) => r.tipo === 'inicio').at(-1)
  const seg = d.riesgos.filter((r) => r.tipo === 'seguimiento')
  const actual = seg.at(-1) ?? ini
  const u = actual && d.umbrales ? d.umbrales[actual.tipo] : null
  const activa = o.estado_operativo === 'ACTIVA'
  const expl = actual ? d.explicaciones[actual.tipo] : undefined
  const suben = (expl ?? []).filter((f) => f.shap > 0)
  const serie = new Map<string, Record<string, number | string>>()
  d.siaf_mensual.forEach((s) => serie.set(s.mes.slice(0, 7), { mes: s.mes.slice(0, 7), devengado: Math.round(s.devengado) }))
  seg.forEach((s) => {
    const k = s.fecha_corte.slice(0, 7)
    serie.set(k, { ...(serie.get(k) ?? { mes: k }), riesgo: Math.round(1000 * s.score) / 10 })
  })
  const datos = [...serie.values()]
    .filter((x) => String(x.mes) >= String(o.fecha_inicio).slice(0, 7) || x.riesgo !== undefined)
    .sort((a, b) => String(a.mes).localeCompare(String(b.mes)))
  const tasaNivel = actual && u ? u.tasa_por_nivel_test[actual.nivel]?.tasa_retraso_observada : undefined
  return (
    <div className="space-y-5">
      <div>
        <Link to="/cartera" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-marca-700">
          <ArrowLeft className="size-4" /> Cartera nacional
        </Link>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
          <h1 className="max-w-4xl text-lg leading-snug font-semibold text-slate-900 sm:text-xl">{o.nombre}</h1>
          {o.cuaderno_id && (
            <Link to={`/obras/${o.cuaderno_id}`} className="btn">
              <FileText className="size-4" /> Ver alerta del cuaderno digital
            </Link>
          )}
        </div>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1.5">
          <Meta icono={<MapPin className="size-4" />}>{[o.distrito, o.provincia, o.departamento].filter(Boolean).map(titulo).join(', ')}</Meta>
          <Meta icono={<Building2 className="size-4" />}>{o.entidad}</Meta>
          <Meta icono={<Tag className="size-4" />}>
            {o.tipo_obra} · {o.modalidad}
          </Meta>
          <Meta icono={<CalendarDays className="size-4" />}>{ESTADO_OP[o.estado_operativo] ?? o.estado_operativo}</Meta>
        </div>
      </div>

      {actual && activa ? (
        <section className="tarjeta overflow-hidden">
          <div className="grid gap-5 p-5 md:grid-cols-[1.1fr_1.6fr]">
            <div>
              <div className="flex items-center gap-1 text-[13px] font-medium text-slate-600">
                Riesgo de terminar con retraso significativo <InfoTip termino="retraso_significativo" />
              </div>
              <div className="mt-2 flex items-baseline gap-3">
                <span className="text-3xl font-semibold tracking-tight" style={{ color: COLOR_NIVEL[actual.nivel] }}>
                  {NIVEL_TEXTO[actual.nivel]}
                </span>
                <span className="num text-lg font-medium text-slate-700">{fmtPct(actual.score)}</span>
                <InfoTip termino="probabilidad" />
              </div>
              <div className="mt-1">
                <VecesPromedio score={actual.score} base={u?.tasa_base_test} />
              </div>
              <div className="mt-1 text-xs text-slate-500">
                {actual.tipo === 'seguimiento' ? `Seguimiento mensual con la ejecución del gasto · corte ${fmtFecha(actual.fecha_corte)}` : `Estimación al inicio de la obra (${fmtFecha(actual.fecha_corte)})`}
              </div>
            </div>
            <div>
              <div className="mb-2 text-[13px] font-medium text-slate-600">Confiabilidad de este nivel</div>
              {u && tasaNivel !== undefined && (
                <p className="text-sm leading-relaxed text-slate-600">
                  Entre las obras evaluadas desde {fmtFecha(u.periodo_test_desde)}, <b className="num text-slate-900">{Math.round(100 * tasaNivel)} de cada 100</b> clasificadas en nivel{' '}
                  {NIVEL_TEXTO[actual.nivel].toLowerCase()} terminaron con retraso significativo; en promedio ocurrió en <span className="num">{Math.round(100 * u.tasa_base_test)}</span> de
                  cada 100. El retraso es frecuente en la cartera, por eso el nivel indica prioridad relativa.
                  <InfoTip termino="confiabilidad" className="ml-1 align-[-2px]" />
                </p>
              )}
            </div>
          </div>
          <div className="border-t border-slate-100 bg-slate-50/70 px-5 py-4">
            <div className="text-[13px] font-medium text-slate-700">Principales factores que elevan el riesgo</div>
            {suben.length ? (
              <ul className="mt-1.5 grid gap-x-6 gap-y-1 text-sm text-slate-800 md:grid-cols-3">
                {suben.slice(0, 3).map((f) => (
                  <li key={f.feature} className="flex gap-2">
                    <span className="mt-2 size-1.5 shrink-0 rounded-full bg-alto" aria-hidden />
                    {f.descripcion}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-1 text-sm text-slate-500">No hay factores que eleven el riesgo registrados para esta estimación.</p>
            )}
          </div>
        </section>
      ) : (
        <div className="tarjeta p-4 text-sm leading-relaxed text-slate-700">
          <b>Resultado observado:</b>{' '}
          {o.retraso_significativo === null
            ? 'aún no determinable con los registros disponibles.'
            : o.retraso_significativo
              ? `la obra tuvo retraso significativo${o.sobreplazo !== null ? ` (se extendió ${fmtPct(o.sobreplazo)} de su plazo original)` : ''}.`
              : 'la obra terminó sin retraso significativo.'}{' '}
          {ini && `La estimación al inicio, hecha sin conocer el resultado, fue ${fmtPct(ini.score)} (riesgo ${NIVEL_TEXTO[ini.nivel].toLowerCase()}).`}
        </div>
      )}

      <Tabs.Root defaultValue="factores">
        <Tabs.List className="pestanas" aria-label="Secciones de la ficha">
          <Tabs.Trigger value="factores" className="pestana">
            Factores
          </Tabs.Trigger>
          <Tabs.Trigger value="gasto" className="pestana">
            Ejecución del gasto
          </Tabs.Trigger>
          <Tabs.Trigger value="datos" className="pestana">
            Datos de la obra
          </Tabs.Trigger>
        </Tabs.List>
        <div className="pt-4">
          <Tabs.Content value="factores">
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
              {(['seguimiento', 'inicio'] as const).map((t) =>
                d.explicaciones[t] ? (
                  <Seccion
                    key={t}
                    ayuda="factor"
                    titulo={t === 'seguimiento' ? 'Estimación de seguimiento mensual' : 'Estimación al inicio de la obra'}
                    subtitulo={
                      t === 'seguimiento'
                        ? `Incluye el avance del plazo y la ejecución del gasto (corte ${fmtFecha(seg.at(-1)?.fecha_corte)}).`
                        : `Solo información conocida al iniciar la obra (${fmtFecha(ini?.fecha_corte)}).`
                    }
                  >
                    <ListaFactores factores={d.explicaciones[t]} />
                  </Seccion>
                ) : null,
              )}
              {!d.explicaciones.seguimiento && !d.explicaciones.inicio && (
                <div className="tarjeta lg:col-span-2">
                  <Vacio titulo="Sin factores explicativos" texto="Las explicaciones se calculan para obras en ejecución e iniciadas desde 2022." />
                </div>
              )}
            </div>
          </Tabs.Content>
          <Tabs.Content value="gasto">
            <Seccion titulo="Ejecución del gasto (SIAF) y riesgo de seguimiento" ayuda="devengado" subtitulo="Barras: gasto devengado mensual de la inversión. Línea: probabilidad estimada cada mes con la información disponible a esa fecha.">
              {datos.length === 0 ? (
                <Vacio titulo="Sin ejecución registrada" texto="La inversión no tiene gasto registrado en SIAF o la obra no tiene código único de inversión propio." />
              ) : (
                <div className="h-80">
                  <ResponsiveContainer>
                    <ComposedChart data={datos} margin={{ left: 6, right: 4, top: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={COLORES.rejilla} />
                      <XAxis dataKey="mes" tick={{ fontSize: 11 }} tickFormatter={(m) => fmtMes(m + '-01')} minTickGap={16} />
                      <YAxis yAxisId="d" tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v / 1e6).toLocaleString('es-PE', { maximumFractionDigits: 1 })} M`} />
                      <YAxis yAxisId="r" orientation="right" domain={[0, 100]} unit="%" tick={{ fontSize: 11 }} />
                      <Tooltip labelFormatter={(m) => fmtMes(m + '-01')} formatter={(v, n) => (n === 'Gasto devengado (S/)' ? fmtMillones(Number(v)) : `${v} %`)} />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <Bar isAnimationActive={false} yAxisId="d" dataKey="devengado" name="Gasto devengado (S/)" fill={COLORES.marcaClaro} radius={[2, 2, 0, 0]} />
                      <Line isAnimationActive={false} yAxisId="r" dataKey="riesgo" name="Riesgo estimado (%)" stroke={COLOR_NIVEL.ALTO} strokeWidth={2} dot={false} connectNulls />
                      {o.fin_programado && <ReferenceLine yAxisId="r" x={String(o.fin_programado).slice(0, 7)} stroke={COLORES.marcaOscuro} strokeDasharray="4 4" label={{ value: 'fin programado', fontSize: 10, position: 'insideTopLeft' }} />}
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              )}
            </Seccion>
          </Tabs.Content>
          <Tabs.Content value="datos">
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
              <Seccion titulo="Datos de la obra (INFOBRAS)" className="lg:col-span-2">
                <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  <Dato l="Entidad" v={o.entidad} />
                  <Dato l="Ejecutor" v={o.contratista} />
                  <Dato l="Costo de obra" v={fmtMillones(o.costo)} />
                  <Dato l="Código INFOBRAS" v={o.codigo_infobras} />
                  <Dato l="Código Único de Inversión" ayuda="cui" v={o.cui} />
                  <Dato l="Inicio" v={fmtFecha(o.fecha_inicio)} />
                  <Dato l="Plazo original" v={o.plazo_dias ? `${fmtNum(o.plazo_dias)} días` : null} />
                  <Dato l="Fin programado" v={fmtFecha(o.fin_programado)} />
                  <Dato l="Fin real" v={fmtFecha(o.fin_real)} />
                </dl>
                {d.contraloria_paralizada.length > 0 && (
                  <div className="mt-4 rounded-lg border border-red-200 bg-alto-suave p-3 text-sm text-red-900">
                    Figura en {d.contraloria_paralizada.length} {d.contraloria_paralizada.length === 1 ? 'reporte' : 'reportes'} de obras paralizadas de la Contraloría (último:{' '}
                    {fmtFecha(d.contraloria_paralizada.at(-1)!.fecha_corte)}).
                  </div>
                )}
              </Seccion>
              <Seccion titulo="Fuentes oficiales">
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
              </Seccion>
            </div>
          </Tabs.Content>
        </div>
      </Tabs.Root>
    </div>
  )
}
