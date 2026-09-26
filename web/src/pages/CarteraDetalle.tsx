import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis, Bar } from 'recharts'
import { api, fmtFecha, fmtMes, fmtMillones, fmtNum, fmtPct, mensajeCartera, type Factor, type Nivel } from '../api'
import { Cargando, ErrorMsg, NivelBadge, Seccion } from '../components/ui'
import { ESTADO_OP } from './Cartera'

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
  infobras: Record<string, any> | null // eslint-disable-line @typescript-eslint/no-explicit-any
  contraloria_paralizada: { fecha_corte: string; avance_fisico: number; causal: string }[]
  enlaces: { fuente: string; url: string }[]
  umbrales: Record<string, Umbral> | null
}

function Factores({ f }: { f: Factor[] }) {
  const max = Math.max(...f.map((x) => Math.abs(x.shap)), 0.001)
  return (
    <ul className="space-y-1.5">
      {f.map((x, i) => (
        <li key={i} className="text-sm">
          <div className="flex items-center gap-2">
            <div className="h-2.5 w-20 shrink-0 rounded bg-slate-100">
              <div className={`h-2.5 rounded ${x.shap > 0 ? 'bg-alto' : 'bg-bajo'}`} style={{ width: `${(100 * Math.abs(x.shap)) / max}%` }} />
            </div>
            <span>{x.descripcion}</span>
          </div>
          <div className="ml-22 text-[11px] text-slate-500">
            {x.grupo} · {x.shap > 0 ? 'aumenta' : 'reduce'} el riesgo ({x.shap > 0 ? '+' : ''}
            {x.shap.toFixed(3)})
          </div>
        </li>
      ))}
    </ul>
  )
}

export default function CarteraDetalle() {
  const { codigo = '' } = useParams()
  const q = useQuery({ queryKey: ['cartera', codigo], queryFn: () => api<Detalle>(`/cartera/${codigo}`) })
  if (q.isLoading) return <Cargando />
  if (q.error) return <ErrorMsg error={q.error} />
  const d = q.data!
  const o = d.obra
  const ini = d.riesgos.filter((r) => r.tipo === 'inicio').at(-1)
  const seg = d.riesgos.filter((r) => r.tipo === 'seguimiento')
  const actual = seg.at(-1) ?? ini
  const serie = new Map<string, Record<string, number | string>>()
  d.siaf_mensual.forEach((s) => serie.set(s.mes.slice(0, 7), { mes: s.mes.slice(0, 7), devengado: Math.round(s.devengado) }))
  seg.forEach((s) => {
    const k = s.fecha_corte.slice(0, 7)
    serie.set(k, { ...(serie.get(k) ?? { mes: k }), riesgo: Math.round(1000 * s.score) / 10 })
  })
  const datos = [...serie.values()].filter((x) => String(x.mes) >= String(o.fecha_inicio).slice(0, 7) || x.riesgo !== undefined).sort((a, b) => String(a.mes).localeCompare(String(b.mes)))
  const u = actual && d.umbrales ? d.umbrales[actual.tipo] : null
  return (
    <div className="space-y-5">
      <div>
        <Link to="/cartera" className="text-sm text-marca-600 hover:underline">
          ← Cartera
        </Link>
        <h1 className="mt-1 text-lg font-bold text-marca-900">{o.nombre}</h1>
        <div className="mt-1 flex flex-wrap items-center gap-3 text-sm text-slate-600">
          {actual && <NivelBadge nivel={actual.nivel} score={actual.score} />}
          <span>{ESTADO_OP[o.estado_operativo] ?? o.estado_operativo}</span>
          <span>
            {o.distrito} · {o.provincia} · {o.departamento}
          </span>
          <span>
            {o.tipo_obra} · {o.modalidad}
          </span>
          <span>Código INFOBRAS {o.codigo_infobras}</span>
          {o.cuaderno_id && (
            <Link to={`/obras/${o.cuaderno_id}`} className="rounded bg-marca-100 px-2 py-0.5 text-marca-700 hover:underline">
              Ver alerta del cuaderno de obra digital
            </Link>
          )}
        </div>
      </div>

      {actual && o.estado_operativo === 'ACTIVA' && (
        <div className={`rounded-xl p-4 text-white ${actual.nivel === 'ALTO' ? 'bg-red-700' : actual.nivel === 'MEDIO' ? 'bg-amber-600' : 'bg-green-700'}`}>
          <div className="text-sm font-semibold">Predicción a futuro</div>
          <p className="mt-1 text-sm">{mensajeCartera(actual.score, actual.tipo)}</p>
          {u && (
            <p className="mt-1 text-xs opacity-90">
              Referencia de validación: entre las obras evaluadas desde {fmtFecha(u.periodo_test_desde)}, el {fmtPct(u.tasa_por_nivel_test[actual.nivel]?.tasa_retraso_observada)} de las
              clasificadas en nivel {actual.nivel} terminó con retraso significativo (tasa base {fmtPct(u.tasa_base_test)}).
            </p>
          )}
        </div>
      )}
      {o.estado_operativo !== 'ACTIVA' && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm">
          <b>Resultado observado:</b>{' '}
          {o.retraso_significativo === null
            ? 'aún no determinable con los registros disponibles.'
            : o.retraso_significativo
              ? `la obra tuvo retraso significativo${o.sobreplazo !== null ? ` (sobre-plazo de ${fmtPct(o.sobreplazo)} del plazo original)` : ''}.`
              : 'la obra terminó sin retraso significativo.'}{' '}
          {ini && `La estimación al inicio (sin conocer el resultado) fue ${fmtPct(ini.score)} (nivel ${ini.nivel}).`}
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-3">
        <Seccion titulo="Datos de la obra">
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <dt className="etiqueta">Entidad</dt>
              <dd>{o.entidad}</dd>
            </div>
            <div>
              <dt className="etiqueta">Ejecutor</dt>
              <dd>{o.contratista ?? '—'}</dd>
            </div>
            <div>
              <dt className="etiqueta">Costo</dt>
              <dd>{fmtMillones(o.costo)}</dd>
            </div>
            <div>
              <dt className="etiqueta">CUI</dt>
              <dd>{o.cui ?? '—'}</dd>
            </div>
            <div>
              <dt className="etiqueta">Inicio</dt>
              <dd>{fmtFecha(o.fecha_inicio)}</dd>
            </div>
            <div>
              <dt className="etiqueta">Plazo original</dt>
              <dd>{fmtNum(o.plazo_dias)} días</dd>
            </div>
            <div>
              <dt className="etiqueta">Fin programado</dt>
              <dd>{fmtFecha(o.fin_programado)}</dd>
            </div>
            <div>
              <dt className="etiqueta">Fin real</dt>
              <dd>{fmtFecha(o.fin_real)}</dd>
            </div>
          </dl>
          <div className="mt-4 space-y-1">
            <div className="etiqueta">Fuentes oficiales</div>
            {d.enlaces.map((e) => (
              <a key={e.url} href={e.url} target="_blank" rel="noopener noreferrer" className="block text-sm text-marca-600 hover:underline">
                {e.fuente} ↗
              </a>
            ))}
          </div>
          {d.contraloria_paralizada.length > 0 && (
            <div className="mt-3 rounded-lg bg-red-50 p-2 text-xs text-red-800">
              Figura en {d.contraloria_paralizada.length} corte(s) del reporte de obras paralizadas de Contraloría (último {fmtFecha(d.contraloria_paralizada.at(-1)!.fecha_corte)}).
            </div>
          )}
        </Seccion>
        <div className="lg:col-span-2">
          <Seccion titulo="Ejecución financiera (SIAF) y riesgo de seguimiento" subtitulo="Barras: devengado mensual de la inversión (S/). Línea: probabilidad estimada cada mes con la información disponible a esa fecha.">
            {datos.length === 0 ? (
              <p className="text-sm text-slate-500">La inversión no tiene ejecución SIAF registrada o no tiene CUI propio.</p>
            ) : (
              <div className="h-72">
                <ResponsiveContainer>
                  <ComposedChart data={datos} margin={{ left: 10, right: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="mes" tick={{ fontSize: 10 }} tickFormatter={(m) => fmtMes(m + '-01')} />
                    <YAxis yAxisId="d" tick={{ fontSize: 10 }} tickFormatter={(v) => `${(v / 1e6).toFixed(1)}M`} />
                    <YAxis yAxisId="r" orientation="right" domain={[0, 100]} unit="%" tick={{ fontSize: 10 }} />
                    <Tooltip />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar isAnimationActive={false} yAxisId="d" dataKey="devengado" name="Devengado (S/)" fill="#94a3b8" />
                    <Line isAnimationActive={false} yAxisId="r" dataKey="riesgo" name="Riesgo (%)" stroke="#b91c1c" strokeWidth={2} connectNulls />
                    {o.fin_programado && <ReferenceLine yAxisId="r" x={String(o.fin_programado).slice(0, 7)} stroke="#1b5f8c" label={{ value: 'fin programado', fontSize: 10 }} />}
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            )}
          </Seccion>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        {(['seguimiento', 'inicio'] as const).map((t) =>
          d.explicaciones[t] ? (
            <Seccion
              key={t}
              titulo={t === 'seguimiento' ? `¿Por qué este riesgo? Seguimiento (${fmtFecha(seg.at(-1)?.fecha_corte)})` : `¿Por qué este riesgo? Al inicio (${fmtFecha(ini?.fecha_corte)})`}
              subtitulo="Contribuciones TreeSHAP calculadas sobre los valores reales de la obra. Rojo aumenta el riesgo, verde lo reduce."
            >
              <Factores f={d.explicaciones[t]} />
            </Seccion>
          ) : null,
        )}
      </div>
    </div>
  )
}
