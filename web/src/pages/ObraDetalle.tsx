import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState, type ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Bar, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, fmtFecha, fmtMes, fmtNum, fmtSoles, mensajeCuaderno, qs, ROL, type Evidencia, type Factor, type Nivel } from '../api'
import { useAuth } from '../auth'
import { Cargando, ErrorMsg, ESTADOS, NivelBadge, Paginacion, Seccion } from '../components/ui'

interface Detalle {
  obra: Record<string, any> // eslint-disable-line @typescript-eslint/no-explicit-any
  infobras: Record<string, any> | null // eslint-disable-line @typescript-eslint/no-explicit-any
  contraloria_paralizada: { fecha_corte: string; avance_fisico: number; causal: string }[]
  enlaces: { fuente: string; url: string }[]
}
interface Riesgo {
  predicciones: { prediccion_id: number; fecha_corte: string; tipo: string; score: number; nivel: Nivel; alerta: boolean; y_observado: number | null }[]
  actividad_mensual: { mes: string; total: number; ampliaciones: number; suspensiones: number; adicionales: number; atraso_normativo: number }[]
  siaf_mensual: { mes: string; devengado: number }[]
  eventos: { fecha: string; tipo: string; tipo_std: string; nro_asiento: number; titulo: string }[]
}
interface Explicacion {
  prediccion: { id: number; fecha_corte: string; score: number; nivel: Nivel; tipo: string; horizonte_dias: number; umbral_alerta: number; modelo_version: string; y_observado: number | null }
  factores: Factor[]
  evidencia: Evidencia[]
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

const TIPOS = ['AMPLIACION_PLAZO', 'SUSPENSION_PLAZO', 'VALORIZACION_MENOR_80', 'CALENDARIO_ACELERADO', 'ADICIONALES', 'VALORIZACIONES', 'CONSULTAS', 'PENALIDADES', 'ORDENES', 'OTRAS_OCURRENCIAS']

function Dato({ l, v }: { l: string; v: React.ReactNode }) {
  return (
    <div>
      <div className="etiqueta">{l}</div>
      <div className="text-sm">{v ?? '—'}</div>
    </div>
  )
}

export default function ObraDetalle() {
  const { id = '' } = useParams()
  const d = useQuery({ queryKey: ['obra', id], queryFn: () => api<Detalle>(`/obras/${id}`) })
  const r = useQuery({ queryKey: ['riesgo', id], queryFn: () => api<Riesgo>(`/obras/${id}/riesgo`) })
  const modelo = useQuery({ queryKey: ['modelo'], queryFn: () => api<{ umbral_alerta: number; horizonte_dias: number; metricas: { umbral_alto?: number } }>('/modelo') })
  const [sel, setSel] = useState<number | null>(null)
  const preds = r.data?.predicciones ?? []
  const pid = sel ?? preds.at(-1)?.prediccion_id ?? null
  const ex = useQuery({ queryKey: ['exp', pid], queryFn: () => api<Explicacion>(`/predicciones/${pid}`), enabled: pid !== null })

  const serie = useMemo(() => {
    const m = new Map<string, Record<string, number | string | null>>()
    for (const a of r.data?.actividad_mensual ?? []) m.set(a.mes.slice(0, 7), { mes: a.mes.slice(0, 7), asientos: a.total, ampliaciones: a.ampliaciones, suspensiones: a.suspensiones })
    for (const p of preds) {
      const k = p.fecha_corte.slice(0, 7)
      m.set(k, { ...(m.get(k) ?? { mes: k }), riesgo: Math.round(1000 * p.score) / 10 })
    }
    return [...m.values()].sort((a, b) => String(a.mes).localeCompare(String(b.mes)))
  }, [r.data, preds])

  if (d.isLoading) return <Cargando />
  if (d.error) return <ErrorMsg error={d.error} />
  const o = d.data!.obra
  const onset = o.fecha_atraso ? String(o.fecha_atraso).slice(0, 7) : null
  return (
    <div className="space-y-5">
      <div>
        <Link to="/obras" className="text-sm text-marca-600 hover:underline">
          ← Obras
        </Link>
        <h1 className="mt-1 text-lg font-bold text-marca-900">{o.denominacion}</h1>
        <div className="mt-1 flex flex-wrap items-center gap-3 text-sm text-slate-600">
          <NivelBadge nivel={o.nivel} score={o.score} />
          <span>{ESTADOS[o.estado_observado] ?? o.estado_observado}</span>
          <span>
            {o.provincia} · {o.distrito}
          </span>
          <span>{o.sector}</span>
          {o.fecha_atraso && <span className="font-medium text-alto">Atraso normativo registrado el {fmtFecha(o.fecha_atraso)}</span>}
        </div>
      </div>

      {o.tipo_prediccion === 'vigente' && o.score !== null && (
        <div className={`flex flex-wrap items-center gap-4 rounded-xl p-4 text-white ${o.nivel === 'ALTO' ? 'bg-red-700' : o.nivel === 'MEDIO' ? 'bg-amber-600' : 'bg-green-700'}`}>
          <div className="text-4xl font-bold">{(100 * o.score).toFixed(0)}%</div>
          <div className="min-w-64 flex-1">
            <div className="text-sm font-semibold">Predicción a 60 días · corte {fmtFecha(o.fecha_corte)}</div>
            <p className="text-sm">{mensajeCuaderno(o.score, o.fecha_atraso)}</p>
          </div>
          <a href={`/api/v1/obras/${o.cuaderno_id}/informe-pdf`} className="rounded-lg bg-white px-4 py-2 text-sm font-semibold text-marca-900 hover:bg-slate-100">
            Descargar informe técnico (PDF)
          </a>
        </div>
      )}
      {o.tipo_prediccion !== 'vigente' && (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white p-4 text-sm">
          <span>
            Obra sin predicción vigente ({o.fecha_atraso ? `atraso formal registrado el ${fmtFecha(o.fecha_atraso)}` : 'culminada, resuelta o sin actividad reciente'}): se
            muestra en modo histórico.
          </span>
          {o.score !== null && (
            <a href={`/api/v1/obras/${o.cuaderno_id}/informe-pdf`} className="btn ml-auto">
              Descargar informe técnico (PDF)
            </a>
          )}
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-3">
        <Seccion titulo="Datos integrados de la obra">
          <div className="grid grid-cols-2 gap-3">
            <Dato l="Entidad" v={o.entidad} />
            <Dato l="Contratista" v={o.contratista} />
            <Dato l="CUI (Invierte.pe)" v={o.cui ? `${o.cui} (${o.cui_metodo_enlace})` : 'no enlazado'} />
            <Dato l="Función / nivel" v={o.funcion ? `${o.funcion} · ${o.nivel_gobierno}` : null} />
            <Dato l="Monto viable" v={fmtSoles(o.monto_viable)} />
            <Dato l="Monto del contrato" v={fmtSoles(o.monto_contrato)} />
            <Dato l="Plazo original" v={o.plazo_original_dias ? `${o.plazo_original_dias} días` : null} />
            <Dato l="Asientos" v={`${fmtNum(o.n_asientos)} (${fmtFecha(o.primer_asiento)} – ${fmtFecha(o.ultimo_asiento)})`} />
          </div>
          <div className="mt-4 space-y-1">
            <div className="etiqueta">Fuentes oficiales</div>
            {d.data!.enlaces.map((e) => (
              <a key={e.url} href={e.url} target="_blank" rel="noopener noreferrer" className="block text-sm text-marca-600 hover:underline">
                {e.fuente} ↗
              </a>
            ))}
            {d.data!.contraloria_paralizada.length > 0 && (
              <div className="mt-2 rounded-lg bg-red-50 p-2 text-xs text-red-800">
                Figura en {d.data!.contraloria_paralizada.length} corte(s) del reporte de obras paralizadas de Contraloría (último:{' '}
                {fmtFecha(d.data!.contraloria_paralizada.at(-1)!.fecha_corte)}, causal: {d.data!.contraloria_paralizada.at(-1)!.causal}).
              </div>
            )}
            {d.data!.infobras && (
              <div className="mt-2 text-xs text-slate-500">
                INFOBRAS (foto al {fmtFecha(d.data!.infobras.fecha_consulta)}): {d.data!.infobras.estado_ejecucion}, avance real {fmtNum(d.data!.infobras.avance_fisico_real, 1)}% vs programado{' '}
                {fmtNum(d.data!.infobras.avance_fisico_programado, 1)}%. Dato informativo: no se usa para predecir.
              </div>
            )}
          </div>
        </Seccion>
        <div className="lg:col-span-2">
          <Seccion
            titulo="Evolución del riesgo estimado"
            subtitulo={`Cada punto es la probabilidad de atraso normativo en los ${modelo.data?.horizonte_dias ?? 60} días siguientes, calculada solo con información disponible en esa fecha. Barras: asientos del mes.`}
          >
            {r.isLoading ? (
              <Cargando />
            ) : (
              <div className="h-72">
                <ResponsiveContainer>
                  <ComposedChart data={serie} margin={{ left: -10, right: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="mes" tick={{ fontSize: 11 }} />
                    <YAxis yAxisId="a" tick={{ fontSize: 11 }} />
                    <YAxis yAxisId="r" orientation="right" domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
                    <Tooltip />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar isAnimationActive={false} yAxisId="a" dataKey="asientos" name="Asientos" fill="#cbd5e1" />
                    <Bar isAnimationActive={false} yAxisId="a" dataKey="suspensiones" name="Suspensiones" fill="#94a3b8" />
                    <Line isAnimationActive={false} yAxisId="r" dataKey="riesgo" name="Riesgo (%)" stroke="#b91c1c" strokeWidth={2} connectNulls />
                    {modelo.data && <ReferenceLine yAxisId="r" y={100 * modelo.data.umbral_alerta} stroke="#d97706" strokeDasharray="4 4" label={{ value: 'umbral de alerta', fontSize: 10, fill: '#d97706' }} />}
                    {onset && <ReferenceLine yAxisId="r" x={onset} stroke="#b91c1c" label={{ value: 'atraso normativo', fontSize: 10, fill: '#b91c1c' }} />}
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            )}
            {preds.length > 0 && (
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                <span className="etiqueta">Ver explicación del corte:</span>
                {preds.map((p) => (
                  <button
                    key={p.prediccion_id}
                    onClick={() => setSel(p.prediccion_id)}
                    className={`rounded px-2 py-0.5 ring-1 ${p.prediccion_id === pid ? 'bg-marca-700 text-white ring-marca-700' : 'ring-slate-300 hover:bg-slate-100'}`}
                  >
                    {fmtMes(p.fecha_corte)}
                    {p.alerta ? ' ●' : ''}
                  </button>
                ))}
              </div>
            )}
          </Seccion>
        </div>
      </div>

      {pid && <ExplicacionPanel data={ex.data} loading={ex.isLoading} error={ex.error} cuadernoId={id} />}
      <Asientos id={id} eventos={r.data?.eventos ?? []} />
    </div>
  )
}

function ExplicacionPanel({ data, loading, error, cuadernoId }: { data?: Explicacion; loading: boolean; error: unknown; cuadernoId: string }) {
  if (loading) return <Cargando texto="Calculando explicación…" />
  if (error) return <ErrorMsg error={error} />
  if (!data) return null
  const p = data.prediccion
  const max = Math.max(...data.factores.map((f) => Math.abs(f.shap)), 0.001)
  const porFeature = new Map<string, Evidencia[]>()
  data.evidencia.forEach((e) => porFeature.set(e.feature, [...(porFeature.get(e.feature) ?? []), e]))
  return (
    <div className="grid gap-5 lg:grid-cols-5">
      <div className="lg:col-span-2">
        <Seccion
          titulo={`¿Por qué este nivel de riesgo? (corte ${fmtFecha(p.fecha_corte)})`}
          subtitulo={`Contribuciones TreeSHAP (log-odds) del modelo ${p.modelo_version}. Rojo aumenta el riesgo, verde lo reduce.`}
        >
          <div className="mb-3 flex items-center gap-2 text-sm">
            <NivelBadge nivel={p.nivel} score={p.score} />
            <span className="text-xs text-slate-500">
              {p.tipo === 'vigente' ? 'predicción vigente' : 'predicción histórica (as-of)'}
              {p.y_observado !== null && ` · resultado observado: ${p.y_observado === 1 ? 'hubo atraso normativo en el horizonte' : 'no hubo atraso en el horizonte'}`}
            </span>
          </div>
          <ul className="space-y-2">
            {data.factores.map((f) => (
              <li key={f.rango} className="text-sm">
                <div className="flex items-center gap-2">
                  <div className="h-2.5 w-24 shrink-0 rounded bg-slate-100">
                    <div className={`h-2.5 rounded ${f.shap > 0 ? 'bg-alto' : 'bg-bajo'}`} style={{ width: `${(100 * Math.abs(f.shap)) / max}%` }} />
                  </div>
                  <span>{f.descripcion}</span>
                </div>
                <div className="ml-26 text-[11px] text-slate-500">
                  {f.grupo} · SHAP {f.shap > 0 ? '+' : ''}
                  {f.shap.toFixed(3)}
                </div>
              </li>
            ))}
          </ul>
          <Simulador prediccionId={p.id} />
          <Revision cuadernoId={cuadernoId} fechaCorte={p.fecha_corte} />
        </Seccion>
      </div>
      <div className="lg:col-span-3">
        <Seccion titulo="Evidencia que respalda la alerta" subtitulo="Registros oficiales asociados a los factores que aumentan el riesgo (asientos del cuaderno de obra, SIAF, seguimiento F12B, historial).">
          {data.evidencia.length === 0 ? (
            <p className="text-sm text-slate-500">Esta predicción no tiene factores de aumento de riesgo con evidencia documental asociada.</p>
          ) : (
            <div className="max-h-[560px] space-y-4 overflow-y-auto pr-1">
              {data.factores
                .filter((f) => f.shap > 0 && porFeature.has(f.feature!))
                .map((f) => (
                  <div key={f.feature}>
                    <div className="mb-1 text-xs font-semibold text-slate-600">{f.descripcion}</div>
                    <ul className="space-y-1.5">
                      {porFeature.get(f.feature!)!.map((e, i) => (
                        <li key={i} className="rounded-lg border border-slate-100 bg-slate-50 p-2 text-xs">
                          <div className="mb-0.5 text-[11px] text-slate-500">
                            {e.fuente === 'ASIENTO' ? `Asiento N° ${e.nro_asiento} · ${e.tipo} · ${ROL[e.rol ?? ''] ?? e.rol ?? ''}` : e.fuente} · {fmtFecha(e.fecha)}
                            {e.archivo_fuente && ` · fuente: ${e.archivo_fuente}`}
                            {e.referencia?.startsWith('http') && (
                              <>
                                {' · '}
                                <a className="text-marca-600 hover:underline" href={e.referencia} target="_blank" rel="noopener noreferrer">
                                  ver fuente ↗
                                </a>
                              </>
                            )}
                          </div>
                          <div className="whitespace-pre-line text-slate-700">{e.extracto}</div>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
            </div>
          )}
        </Seccion>
      </div>
    </div>
  )
}

function Revision({ cuadernoId, fechaCorte }: { cuadernoId: string; fechaCorte: string }) {
  const { usuario } = useAuth()
  const qc = useQueryClient()
  const [decision, setDecision] = useState('EN_SEGUIMIENTO')
  const [comentario, setComentario] = useState('')
  const key = ['rev', cuadernoId, fechaCorte]
  const q = useQuery({ queryKey: key, queryFn: () => api<{ id: number; decision: string; comentario: string; creado_en: string; usuario: string }[]>(`/alertas/${cuadernoId}/${fechaCorte}/revisiones`), enabled: !!usuario })
  const m = useMutation({
    mutationFn: () => api(`/alertas/${cuadernoId}/${fechaCorte}/revisiones`, { method: 'POST', body: JSON.stringify({ decision, comentario: comentario || null }) }),
    onSuccess: () => {
      setComentario('')
      qc.invalidateQueries({ queryKey: key })
      qc.invalidateQueries({ queryKey: ['alertas'] })
    },
  })
  if (!usuario)
    return (
      <p className="mt-4 text-xs text-slate-500">
        <Link to="/login" className="text-marca-600 underline">
          Ingrese
        </Link>{' '}
        como analista para registrar la revisión de esta alerta.
      </p>
    )
  return (
    <div className="mt-4 border-t border-slate-100 pt-3">
      <div className="etiqueta mb-2">Revisión del analista</div>
      <div className="flex flex-wrap gap-2">
        <select className="entrada" aria-label="Decisión de la revisión" value={decision} onChange={(e) => setDecision(e.target.value)}>
          <option value="EN_SEGUIMIENTO">En seguimiento</option>
          <option value="CONFIRMADA">Confirmada</option>
          <option value="DESCARTADA">Descartada</option>
        </select>
        <input className="entrada flex-1" placeholder="Comentario (opcional)" maxLength={2000} value={comentario} onChange={(e) => setComentario(e.target.value)} />
        <button className="btn-primario" disabled={m.isPending} onClick={() => m.mutate()}>
          Registrar
        </button>
      </div>
      {m.error && <p className="mt-1 text-xs text-red-700">{String((m.error as Error).message)}</p>}
      <ul className="mt-2 space-y-1 text-xs text-slate-600">
        {(q.data ?? []).map((x) => (
          <li key={x.id}>
            <b>{x.decision}</b> · {x.usuario} · {fmtFecha(x.creado_en)} {x.comentario ? `— ${x.comentario}` : ''}
          </li>
        ))}
      </ul>
    </div>
  )
}

function Simulador({ prediccionId }: { prediccionId: number }) {
  const q = useQuery({
    queryKey: ['sim', prediccionId],
    queryFn: () => api<{ escenario: string; descripcion: string; score_base: number; score_escenario: number; alerta_escenario: boolean }[]>(`/predicciones/${prediccionId}/simulacion`),
  })
  if (!q.data || q.data.length === 0) return null
  return (
    <div className="mt-4 border-t border-slate-100 pt-3">
      <div className="etiqueta mb-1">Simulador de intervención (sensibilidad del modelo)</div>
      <p className="mb-2 text-xs text-slate-500">Probabilidad recalculada cambiando una sola señal. Indica de qué depende la estimación; no garantiza el efecto real de una acción.</p>
      <ul className="space-y-2">
        {q.data.map((s) => (
          <li key={s.escenario} className="text-sm">
            <div>
              Escenario «{s.descripcion}»: el riesgo estimado pasaría de {(100 * s.score_base).toFixed(0)}% a{' '}
              <b className={s.score_escenario < s.score_base ? 'text-bajo' : 'text-alto'}>{(100 * s.score_escenario).toFixed(0)}%</b>.
            </div>
            <div className="mt-1 flex h-2 overflow-hidden rounded bg-slate-100">
              <div className="bg-slate-400" style={{ width: `${100 * Math.min(s.score_base, s.score_escenario)}%` }} />
              <div className={s.score_escenario < s.score_base ? 'bg-green-300' : 'bg-red-300'} style={{ width: `${100 * Math.abs(s.score_base - s.score_escenario)}%` }} />
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

const CRITICOS: [RegExp, string][] = [
  [/(falta de personal|ausencia del (residente|especialista|ingeniero)|personal insuficiente|no se encuentra (el )?(residente|especialista))/gi, 'bg-red-200'],
  [/(maquinaria|equipo (inoperativo|malogrado|averiado)|falla mec[aá]nica)/gi, 'bg-orange-200'],
  [/(incompatibilidad|deficiencias? (del|en el) expediente|error(es)? en (el )?expediente|vicios ocultos)/gi, 'bg-purple-200'],
  [/(falta de pago|pago pendiente|adelanto|desabastec|falta de material)/gi, 'bg-yellow-200'],
  [/(paraliz|atras|retras|demora|incumpl|penalidad)/gi, 'bg-rose-200'],
  [/(lluvia|precipitaci)/gi, 'bg-sky-200'],
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
      <mark key={k} className={`${m.c} rounded px-0.5`}>
        {texto.slice(m.i, m.f)}
      </mark>,
    )
    pos = m.f
  })
  out.push(texto.slice(pos))
  return <>{out}</>
}

function Asientos({ id, eventos }: { id: string; eventos: Riesgo['eventos'] }) {
  const [pagina, setPagina] = useState(1)
  const [tipo, setTipo] = useState('')
  const [q, setQ] = useState('')
  const [buscar, setBuscar] = useState('')
  const [abierto, setAbierto] = useState<number | null>(null)
  const [auditoria, setAuditoria] = useState(false)
  const r = useQuery({ queryKey: ['asientos', id, tipo, buscar, pagina], queryFn: () => api<{ total: number; items: Asiento[] }>(`/obras/${id}/asientos${qs({ tipo, q: buscar, pagina, tamanio: 15 })}`) })
  return (
    <div className="grid gap-5 lg:grid-cols-4">
      <Seccion titulo="Hitos del cuaderno">
        <ul className="space-y-1.5 text-xs">
          {eventos.length === 0 && <li className="text-slate-500">Sin hitos registrados.</li>}
          {eventos.map((e, i) => (
            <li key={i} className={['VALORIZACION_MENOR_80', 'CALENDARIO_ACELERADO', 'RESOLUCION_CONTRATO'].includes(e.tipo_std) ? 'font-medium text-alto' : ''}>
              {fmtFecha(e.fecha)} · {e.tipo} (N° {e.nro_asiento})
            </li>
          ))}
        </ul>
      </Seccion>
      <div className="lg:col-span-3">
        <Seccion
          titulo="Asientos del cuaderno de obra digital"
          subtitulo="Registros publicados por OECE (datos abiertos). Búsqueda de texto completo en español. El modo auditoría resalta menciones de personal, maquinaria, expediente, pagos y materiales, atrasos e incumplimientos, y clima."
        >
          <form
            className="mb-3 flex flex-wrap gap-2"
            onSubmit={(e) => {
              e.preventDefault()
              setBuscar(q)
              setPagina(1)
            }}
          >
            <input className="entrada flex-1" aria-label="Buscar en los asientos" placeholder="Buscar en los asientos (p.ej. lluvias, falta de pago, expediente)" value={q} maxLength={200} onChange={(e) => setQ(e.target.value)} />
            <select aria-label="Tipo de asiento"
              className="entrada"
              value={tipo}
              onChange={(e) => {
                setTipo(e.target.value)
                setPagina(1)
              }}
            >
              <option value="">Todos los tipos</option>
              {TIPOS.map((t) => (
                <option key={t} value={t}>
                  {t.replace(/_/g, ' ').toLowerCase()}
                </option>
              ))}
            </select>
            <button className="btn" type="submit">
              Buscar
            </button>
            <label className="flex items-center gap-1 text-sm">
              <input type="checkbox" checked={auditoria} onChange={(e) => setAuditoria(e.target.checked)} /> Modo auditoría
            </label>
          </form>
          {r.isLoading ? (
            <Cargando />
          ) : r.error ? (
            <ErrorMsg error={r.error} />
          ) : (
            <>
              <ul className="space-y-2">
                {r.data!.items.map((a) => (
                  <li key={a.id} className="rounded-lg border border-slate-100 p-2">
                    <button className="w-full text-left" onClick={() => setAbierto(abierto === a.id ? null : a.id)}>
                      <div className="text-[11px] text-slate-500">
                        {fmtFecha(a.fecha)} · N° {a.nro_asiento} · {a.tipo} · {ROL[a.rol] ?? a.rol}
                      </div>
                      <div className="text-sm font-medium">{a.titulo}</div>
                    </button>
                    <div className={`mt-1 whitespace-pre-line text-xs text-slate-700 ${abierto === a.id || auditoria ? '' : 'line-clamp-2'}`}>
                      <Resaltado texto={a.descripcion} activo={auditoria} />
                    </div>
                  </li>
                ))}
              </ul>
              <Paginacion pagina={pagina} total={r.data!.total} tamanio={15} onChange={setPagina} />
            </>
          )}
        </Seccion>
      </div>
    </div>
  )
}
