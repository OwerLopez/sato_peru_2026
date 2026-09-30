import { useQuery } from '@tanstack/react-query'
import { AlertCircle, CheckCircle2, Info, OctagonAlert, RefreshCw, XCircle } from 'lucide-react'
import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, fmtDec, fmtFecha, fmtMes, fmtNum, fmtPct, useEstado, type Carga, type EstadoGeneral, type EstadoSistema, type Monitoreo } from '../api'
import { Cargando, CargandoPagina, EncabezadoPagina, ErrorMsg, InfoTip, Kpi, Panel, Seccion, Segmentado, Vacio } from '../components/ui'
import { COLOR_NIVEL, COLORES } from '../lib/colores'

const ESTADO: Record<EstadoGeneral, { texto: string; clase: string; icono: typeof CheckCircle2 }> = {
  OPERATIVO: { texto: 'Operativo', clase: 'border-green-200 bg-bajo-suave text-green-900', icono: CheckCircle2 },
  CON_AVISOS: { texto: 'Operativo con avisos', clase: 'border-amber-200 bg-medio-suave text-amber-900', icono: AlertCircle },
  DEGRADADO: { texto: 'Degradado', clase: 'border-red-200 bg-alto-suave text-red-900', icono: OctagonAlert },
}
const ICONO_MOTIVO = { INFO: Info, AVISO: AlertCircle, CRITICO: XCircle } as const
const COLOR_MOTIVO = { INFO: 'text-slate-400', AVISO: 'text-medio', CRITICO: 'text-alto' } as const
const ESTADO_CARGA_CORTO: Record<Carga['estado'], string> = { OK: 'Aplicada', RECHAZADA: 'Rechazada', ERROR: 'Con error', EN_CURSO: 'En curso' }
const ESTADO_CARGA: Record<Carga['estado'], string> = { OK: 'Aplicada', RECHAZADA: 'Rechazada por la compuerta', ERROR: 'Error', EN_CURSO: 'En curso' }
const TABLAS: Record<string, string> = {
  obra: 'Obras con cuaderno digital',
  asiento: 'Asientos del cuaderno',
  prediccion: 'Estimaciones de riesgo (alerta 60 días)',
  explicacion: 'Factores explicativos',
  evidencia: 'Evidencia documental',
  simulacion: 'Escenarios de sensibilidad',
  inversion: 'Inversiones públicas (MEF)',
  siaf_mensual: 'Ejecución mensual SIAF',
  infobras_obra: 'Fichas INFOBRAS',
  contraloria_paralizada: 'Obras paralizadas (Contraloría)',
  mef_seguimiento: 'Seguimiento F12B (MEF)',
  cartera_obra: 'Cartera INFOBRAS',
  cartera_riesgo: 'Estimaciones de la cartera',
  cartera_explicacion: 'Factores de la cartera',
}

export function IndicadorEstado({ e }: { e: EstadoSistema | undefined }) {
  if (!e) return null
  const x = ESTADO[e.estado]
  return (
    <span className="inline-flex items-center gap-1.5">
      <x.icono className="size-3.5" aria-hidden />
      {x.texto}
    </span>
  )
}

function Semaforo({ e }: { e: EstadoSistema }) {
  const x = ESTADO[e.estado]
  return (
    <section className={`rounded-xl border p-4 ${x.clase}`} aria-live="polite">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-base font-semibold">
          <x.icono className="size-5" aria-hidden />
          Estado de la plataforma: {x.texto.toLowerCase()}
        </h2>
        <span className="text-xs opacity-80">Verificado {new Date(e.verificado_en).toLocaleString('es-PE')}</span>
      </div>
      {e.motivos.length === 0 ? (
        <p className="mt-1 text-sm">Todos los componentes responden y no hay hallazgos pendientes.</p>
      ) : (
        <ul className="mt-2 space-y-1.5">
          {e.motivos.map((m, i) => {
            const I = ICONO_MOTIVO[m.nivel]
            return (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-800">
                <I className={`mt-0.5 size-4 shrink-0 ${COLOR_MOTIVO[m.nivel]}`} aria-label={m.nivel === 'INFO' ? 'Información' : m.nivel === 'AVISO' ? 'Aviso' : 'Crítico'} />
                {m.texto}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

function Desempeno({ m }: { m: Monitoreo }) {
  const [vista, setVista] = useState<'grafico' | 'tabla'>('grafico')
  const d = m.desempeno_realizado.map((x) => ({ ...x, pct: +(100 * x.recall_alerta).toFixed(1) }))
  if (!d.length) return <Vacio titulo="Aún no hay cortes con resultado conocido" />
  const total = d.reduce((a, x) => a + x.eventos, 0)
  const anticip = d.reduce((a, x) => a + x.recall_alerta * x.eventos, 0)
  return (
    <Seccion
      titulo="¿El modelo sigue anticipando los atrasos?"
      ayuda="deteccion"
      subtitulo={`Cortes mensuales cuyo plazo de 60 días ya venció. En conjunto, ${fmtPct(total ? anticip / total : null)} de los ${fmtNum(total)} atrasos formales ya estaban en nivel alto.`}
      accion={<Segmentado etiqueta="Vista" valor={vista} onChange={setVista} opciones={[{ v: 'grafico', l: 'Gráfico' }, { v: 'tabla', l: 'Tabla' }]} />}
    >
      {vista === 'grafico' ? (
        <div className="h-64" role="img" aria-label="Proporción de atrasos anticipados por corte mensual">
          <ResponsiveContainer>
            <LineChart data={d} margin={{ left: -14, right: 12, top: 8, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={COLORES.rejilla} />
              <XAxis dataKey="T" tickFormatter={(t) => fmtMes(t)} tick={{ fontSize: 11 }} minTickGap={24} />
              <YAxis unit="%" domain={[0, 100]} tick={{ fontSize: 11 }} />
              <Tooltip
                formatter={(v, _n, p) => [`${v} % (${(p.payload as { eventos: number }).eventos} atrasos)`, 'Anticipados en nivel alto']}
                labelFormatter={(l) => `Corte ${fmtFecha(String(l))}`}
              />
              <Line isAnimationActive={false} dataKey="pct" stroke={COLORES.marca} strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="max-h-64 overflow-auto">
          <table className="tabla">
            <thead>
              <tr>
                <th>Corte</th>
                <th className="text-right">Obras evaluadas</th>
                <th className="text-right">Atrasos ocurridos</th>
                <th className="text-right">Anticipados</th>
                <th className="text-right">PR-AUC</th>
              </tr>
            </thead>
            <tbody>
              {[...d].reverse().map((x) => (
                <tr key={x.T}>
                  <td>{fmtFecha(x.T)}</td>
                  <td className="num text-right">{fmtNum(x.n)}</td>
                  <td className="num text-right">{fmtNum(x.eventos)}</td>
                  <td className="num text-right">{fmtPct(x.recall_alerta)}</td>
                  <td className="num text-right">{fmtDec(x.pr_auc, 3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="mt-2 text-xs text-slate-500">Cada corte tiene pocas obras con atraso, por lo que la proporción varía de un mes a otro; la tendencia de varios meses es más informativa que un mes aislado.</p>
    </Seccion>
  )
}

function Deriva({ m }: { m: Monitoreo }) {
  const d = (m.psi_detalle ?? []).slice(0, 10).map((x) => ({ ...x, psi: +x.psi.toFixed(2) }))
  if (!d.length) return null
  const altos = d.filter((x) => x.psi > 0.25).length
  return (
    <Seccion
      titulo="¿Cambiaron los datos de entrada del modelo?"
      ayuda="deriva"
      subtitulo={
        altos
          ? `${altos} de las variables más cambiantes superan el umbral de cambio grande (0,25; línea punteada) frente al periodo de entrenamiento: conviene evaluar un reentrenamiento.`
          : 'Ninguna variable supera el umbral de cambio grande (0,25; línea punteada) frente al periodo de entrenamiento.'
      }
    >
      <div style={{ height: 36 * d.length + 36 }} role="img" aria-label="Índice de cambio por variable">
        <ResponsiveContainer>
          <BarChart data={d} layout="vertical" margin={{ left: 8, right: 36, top: 4, bottom: 4 }} barCategoryGap={8}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke={COLORES.rejilla} />
            <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => fmtDec(v, 2)} />
            <YAxis type="category" dataKey="etiqueta" width={230} tick={{ fontSize: 11, fill: '#334155' }} />
            <Tooltip formatter={(v) => [fmtDec(Number(v), 2), 'Índice de cambio (PSI)']} />
            <ReferenceLine x={0.25} stroke={COLOR_NIVEL.MEDIO} strokeDasharray="4 3" />
            <Bar isAnimationActive={false} dataKey="psi" radius={[0, 4, 4, 0]} label={{ position: 'right', fontSize: 11, fill: '#334155', formatter: (v: unknown) => fmtDec(Number(v), 2) }}>
              {d.map((x) => (
                <Cell key={x.variable} fill={x.psi > 0.25 ? COLORES.marcaOscuro : COLORES.marcaClaro} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-slate-500">
        Un cambio grande no significa que el modelo esté equivocado: puede reflejar que la cartera actual es distinta (por ejemplo, obras más recientes con menos plazo transcurrido). Se
        contrasta con el desempeño realizado de la sección anterior antes de decidir un reentrenamiento.
      </p>
    </Seccion>
  )
}

function Anomalia({ m }: { m: Monitoreo }) {
  const a = m.anomalia_nivel_alto
  if (!a) return null
  if (!a.evaluable) return <Seccion titulo="¿Es normal la cantidad de obras en nivel alto?"><p className="text-sm text-slate-600">No evaluable: {a.motivo}.</p></Seccion>
  const d = (a.serie ?? []).map((x) => ({ ...x, pct: +(100 * x.tasa).toFixed(1) }))
  return (
    <Seccion
      titulo="¿Es normal la cantidad de obras en nivel alto?"
      subtitulo={`Corte vigente (${fmtFecha(a.corte)}): ${fmtPct(a.tasa, 1)} de obras en nivel alto frente a una mediana histórica de ${fmtPct(a.mediana, 1)}. ${
        a.anomala ? 'Es un valor atípico: revisar las fuentes antes de difundir.' : 'Está dentro del rango habitual.'
      }`}
    >
      <div className="h-52" role="img" aria-label="Proporción de obras en nivel alto por corte">
        <ResponsiveContainer>
          <LineChart data={d} margin={{ left: -14, right: 12, top: 8, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={COLORES.rejilla} />
            <XAxis dataKey="T" tickFormatter={(t) => fmtMes(t)} tick={{ fontSize: 11 }} minTickGap={24} />
            <YAxis unit="%" tick={{ fontSize: 11 }} />
            <Tooltip formatter={(v, _n, p) => [`${v} %`, (p.payload as { tipo: string }).tipo === 'vigente' ? 'Corte vigente' : 'Validación histórica']} labelFormatter={(l) => fmtFecha(String(l))} />
            <ReferenceLine y={+(100 * (a.mediana ?? 0)).toFixed(1)} stroke={COLORES.gris} strokeDasharray="4 3" label={{ value: 'Mediana', fontSize: 10, fill: '#64748b', position: 'insideTopLeft' }} />
            <Line
              isAnimationActive={false}
              dataKey="pct"
              stroke={COLORES.marca}
              strokeWidth={2}
              dot={(p: { cx?: number; cy?: number; index?: number; payload?: { tipo: string } }) => (
                <circle key={p.index} cx={p.cx} cy={p.cy} r={p.payload?.tipo === 'vigente' ? 5 : 2.5} fill={p.payload?.tipo === 'vigente' ? COLORES.marcaOscuro : COLORES.marca} stroke="#fff" strokeWidth={2} />
              )}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-xs text-slate-500">
        Detección automática: puntaje z robusto {fmtDec(a.z, 1)} (se marca como atípico por encima de {fmtDec(a.umbral_z, 1)} en valor absoluto), calculado con {a.cortes_historicos} cortes de validación.
      </p>
    </Seccion>
  )
}

function Cargas() {
  const q = useQuery({ queryKey: ['cargas'], queryFn: () => api<{ items: Carga[] }>('/sistema/cargas') })
  const [sel, setSel] = useState<Carga | null>(null)
  if (q.isLoading) return <Cargando filas={3} />
  if (q.error) return <ErrorMsg error={q.error} reintentar={() => q.refetch()} />
  const items = q.data?.items ?? []
  return (
    <Seccion titulo="Actualizaciones de datos" ayuda="compuerta" subtitulo="Cada carga se valida antes de publicarse. Seleccione una para ver la conciliación de registros." sinRelleno>
      {items.length === 0 ? (
        <Vacio titulo="Sin cargas registradas" texto="El historial comienza con la primera carga hecha con la compuerta de integridad." />
      ) : (
        <div className="overflow-x-auto">
          <table className="tabla">
            <thead>
              <tr>
                <th>Inicio</th>
                <th>Resultado</th>
                <th className="text-right">Duración</th>
                <th className="text-right">Asientos</th>
                <th className="text-right">Estimaciones</th>
                <th><span className="sr-only">Acciones</span></th>
              </tr>
            </thead>
            <tbody>
              {items.map((c) => (
                <tr key={c.id}>
                  <td className="whitespace-nowrap">{new Date(c.inicio).toLocaleString('es-PE', { dateStyle: 'medium', timeStyle: 'short' })}</td>
                  <td className="whitespace-nowrap">
                    <span className={`inline-flex items-center gap-1 text-sm ${c.estado === 'OK' ? 'text-green-800' : c.estado === 'EN_CURSO' ? 'text-slate-600' : 'text-red-800'}`}>
                      {c.estado === 'OK' ? <CheckCircle2 className="size-3.5" /> : c.estado === 'EN_CURSO' ? <RefreshCw className="size-3.5" /> : <XCircle className="size-3.5" />}
                      {ESTADO_CARGA[c.estado]}
                    </span>
                  </td>
                  <td className="num text-right">{c.fin ? `${Math.round((+new Date(c.fin) - +new Date(c.inicio)) / 60000)} min` : '—'}</td>
                  <td className="num text-right">{fmtNum(c.conteos?.asiento)}</td>
                  <td className="num text-right">{fmtNum(c.conteos?.prediccion)}</td>
                  <td className="text-right whitespace-nowrap">
                    <button className="btn btn-sm" onClick={() => setSel(c)}>
                      Ver detalle
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Panel abierto={!!sel} onClose={() => setSel(null)} titulo="Detalle de la actualización" subtitulo={sel ? new Date(sel.inicio).toLocaleString('es-PE') : undefined} ancho="max-w-2xl">
        {sel && <DetalleCarga c={sel} />}
      </Panel>
    </Seccion>
  )
}

function DetalleCarga({ c }: { c: Carga }) {
  const v = c.validacion ?? {}
  const hallazgos = [...(v.entradas ?? []), ...(v.criticos ?? []), ...(v.caidas ?? [])]
  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-sm font-semibold text-slate-900">Compuerta de integridad</h3>
        {hallazgos.length === 0 ? (
          <p className="mt-1 flex items-center gap-1.5 text-sm text-green-800">
            <CheckCircle2 className="size-4" /> Sin hallazgos: entradas completas, chequeos críticos en cero y ninguna tabla clave con caída mayor a {fmtPct(v.max_caida ?? 0.2)}.
          </p>
        ) : (
          <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-700">
            {hallazgos.map((h) => (
              <li key={h}>{h}</li>
            ))}
          </ul>
        )}
        {v.forzada && <p className="mt-1 text-sm text-amber-800">Se aceptó una caída de filas revisada manualmente (SATO_CARGA_FORZAR).</p>}
        {c.mensaje && <p className="mt-1 text-sm text-red-800">{c.mensaje}</p>}
      </div>
      {c.conciliacion && (
        <div>
          <h3 className="flex items-center gap-1.5 text-sm font-semibold text-slate-900">
            Conciliación de registros <InfoTip termino="conciliacion" />
          </h3>
          <div className="mt-2 overflow-x-auto">
            <table className="tabla">
              <thead>
                <tr>
                  <th>Tabla</th>
                  <th className="text-right">Origen</th>
                  <th className="text-right">Cargadas</th>
                  <th className="text-right">Descartadas</th>
                  <th>Motivo del descarte</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(c.conciliacion).map(([t, x]) => (
                  <tr key={t}>
                    <td>{TABLAS[t] ?? t}</td>
                    <td className="num text-right">{fmtNum(x.origen)}</td>
                    <td className="num text-right">{fmtNum(x.cargadas)}</td>
                    <td className="num text-right">{fmtNum(x.descartadas)}</td>
                    <td className="text-xs text-slate-600">{x.descartadas > 0 ? x.motivo : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

export default function Sistema() {
  const e = useEstado()
  const m = useQuery({ queryKey: ['monitoreo'], queryFn: () => api<Monitoreo | null>('/sistema/monitoreo') })
  if (e.isLoading) return <CargandoPagina />
  if (e.error || !e.data) return <ErrorMsg error={e.error ?? 'Sin datos'} reintentar={() => e.refetch()} />
  const s = e.data
  const cal = s.calidad ?? {}
  return (
    <div className="space-y-5">
      <EncabezadoPagina
        titulo="Estado y monitoreo"
        descripcion="Salud de la plataforma calculada en cada consulta: disponibilidad, frescura de los datos, resultado de cada actualización y comportamiento del modelo con datos nuevos."
      />
      <Semaforo e={s} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi titulo="Datos al corte" valor={fmtFecha(s.datos.fecha_corte)} detalle={s.datos.dias_desde_corte !== null ? `Hace ${fmtNum(s.datos.dias_desde_corte)} días` : undefined} />
        <Kpi
          titulo="Última actualización"
          valor={s.carga.ultima ? (ESTADO_CARGA_CORTO[s.carga.ultima.estado as Carga['estado']] ?? s.carga.ultima.estado) : 'Sin registro'}
          detalle={s.carga.ultima ? fmtFecha(s.carga.ultima.inicio) : 'Anterior al historial de cargas'}
        />
        <Kpi
          titulo="Chequeos sin hallazgos"
          valor={`${fmtNum(cal.OK)} de ${fmtNum((cal.OK ?? 0) + (cal.AVISO ?? 0) + (cal.CRITICO ?? 0))}`}
          detalle={`${fmtNum(cal.AVISO)} con hallazgos de la fuente · ${fmtNum(cal.CRITICO ?? 0)} críticos`}
        />
        <Kpi
          titulo="Modelo entrenado hasta"
          valor={s.modelo ? fmtMes(s.modelo.entrenado_hasta) : 'Sin modelo'}
          detalle={s.modelo ? `${s.modelo.variables_con_deriva} variables con cambio grande · base de datos ${fmtDec(s.base_datos.latencia_ms, 1)} ms` : undefined}
        />
      </div>
      {m.isLoading ? (
        <Cargando />
      ) : m.error ? (
        <ErrorMsg error={m.error} reintentar={() => m.refetch()} />
      ) : !m.data ? (
        <Seccion titulo="Monitoreo del modelo">
          <Vacio titulo="Sin reporte de monitoreo" texto="La carga vigente no incluye el reporte del paso de monitoreo (python -m sato.pipeline monitor)." />
        </Seccion>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
            <Desempeno m={m.data} />
            <Anomalia m={m.data} />
          </div>
          <Deriva m={m.data} />
        </>
      )}
      <Cargas />
      <Seccion titulo="Sincronización automática">
        <dl className="grid gap-3 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-slate-500">Última sincronización</dt>
            <dd className="font-medium text-slate-900">{s.sincronizacion ? `${fmtFecha(s.sincronizacion.inicio)} · ${s.sincronizacion.estado}` : 'Sin registros'}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Worker</dt>
            <dd className="font-medium text-slate-900">{s.worker ? `Activo, último reporte ${new Date(s.worker.ultimo_latido).toLocaleString('es-PE')}` : 'No desplegado en este servidor'}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Política</dt>
            <dd className="text-slate-700">Mensual, hasta 3 intentos con espera creciente; avisos por correo al administrador.</dd>
          </div>
        </dl>
      </Seccion>
    </div>
  )
}
