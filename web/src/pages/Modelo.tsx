import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api, fmtFecha, fmtNum, qs } from '../api'
import { Cargando, ErrorMsg, Kpi, Seccion } from '../components/ui'

interface Metricas {
  n: number
  positivos: number
  prevalencia: number
  pr_auc: number
  roc_auc: number
  precision: number
  recall: number
  f2: number
  tp: number
  fp: number
  fn: number
  tn: number
  precision_top10: number
  recall_top10: number
  obras_con_onset_en_test: number
  obras_alertadas_antes_del_onset: number
  anticipacion_mediana_dias: number
}
interface Modelo {
  version: string
  objetivo: string
  horizonte_dias: number
  conjunto_features: string
  algoritmo: string
  entrenado_hasta: string
  umbral_alerta: number
  sha256: string
  features: string[]
  metricas: {
    arequipa: Metricas
    nacional: Metricas
    valid_pr_auc: number
    umbral_alto: number
    umbral_vigilancia?: number
    periodos: Record<string, [string, string, number, number]>
    operacion_backtest_arequipa?: {
      filas_observables: number
      prevalencia: number
      alerta_alto: { tasa_marcadas: number; precision: number; recall: number }
      vigilancia_o_alto: { tasa_marcadas: number; precision: number; recall: number }
      [k: string]: unknown
    }
  }
}
interface Comp {
  horizonte: number
  variante: string
  alcance_test: string
  metrica: string
  a: number
  b: number
  diferencia: number
  ic_inf: number
  ic_sup: number
  p_valor: number
  obras: number
}
interface Exp {
  horizonte: number
  conjunto_features: string
  alcance_entrenamiento: string
  modelo: string
  metricas: Metricas & { valid_pr_auc: number }
}

const f3 = (x?: number | null) => (x === null || x === undefined || Number.isNaN(x) ? '—' : x.toFixed(3))
const DESC: Record<string, string> = {
  A: 'Estructurado (tipos de asiento, actividad, contrato, SIAF, F12B, historial de actores)',
  A_sin_ib: 'A sin atributos INFOBRAS',
  A_asientos: 'Solo metadatos de asientos',
  B_lex: 'A + léxico de causas de atraso',
  B_lex_sinproxy: 'A + léxico sin menciones de la regla del 80%',
  B_ie: 'A + extracción de avances reportados',
  B_lsa: 'A + LSA (TF-IDF + SVD)',
  B_emb: 'A + embeddings Sentence-BERT',
  B_stack_tfidf: 'A + score de texto TF-IDF (as-of)',
  B_stack_emb: 'A + score de embeddings (as-of)',
  B_full: 'A + todo el componente documental',
  B_full_sinproxy: 'B_full sin léxico proxy ni extracción',
}

export default function ModeloPage() {
  const m = useQuery({ queryKey: ['modelo'], queryFn: () => api<Modelo>('/modelo') })
  const c = useQuery({ queryKey: ['comp'], queryFn: () => api<Comp[]>('/investigacion/comparacion?objetivo=atraso') })
  const [scope, setScope] = useState('arequipa')
  const e = useQuery({ queryKey: ['exp', scope], queryFn: () => api<Exp[]>(`/investigacion/experimentos${qs({ objetivo: 'atraso', alcance_test: scope })}`) })
  if (m.isLoading) return <Cargando />
  if (m.error) return <ErrorMsg error={m.error} />
  const md = m.data!
  const ma = md.metricas.arequipa
  const mn = md.metricas.nacional
  const per = md.metricas.periodos
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-marca-900">Modelo y validación científica</h1>
        <p className="text-sm text-slate-500">
          Modelo {md.version} · {md.algoritmo} · horizonte {md.horizonte_dias} días · entrenado con cortes hasta {fmtFecha(md.entrenado_hasta)}
        </p>
      </div>
      <Seccion titulo="Definición del problema">
        <div className="grid gap-4 text-sm md:grid-cols-3">
          <div>
            <div className="etiqueta">Evento objetivo</div>
            <p>
              <b>Atraso significativo normativo</b>: primer asiento del cuaderno de obra digital de tipo «Valorización acumulada ejecutada menor al 80% del monto
              acumulado programado» o «Calendario acelerado de obra» (RLCE, DS 344-2018-EF, art. 203; Reglamento de la Ley 32069, DS 009-2025-EF, art. 207).
            </p>
          </div>
          <div>
            <div className="etiqueta">Unidad y tiempo</div>
            <p>
              Obra-mes. En cada fin de mes T solo se usa información fechada hasta T (asientos ≤ T, devengado SIAF hasta el mes anterior, F12B registrado ≤ T). Se
              predice si el evento ocurrirá en (T, T+{md.horizonte_dias} días].
            </p>
          </div>
          <div>
            <div className="etiqueta">Validación</div>
            <p>
              Holdout temporal ciego: entrenamiento {per?.train?.[0]} a {per?.train?.[1]}, validación {per?.valid?.[0]} a {per?.valid?.[1]}, test {per?.test?.[0]} a{' '}
              {per?.test?.[1]}, con purga de {md.horizonte_dias} días entre periodos. Umbral e hiperparámetros elegidos solo en validación.
            </p>
          </div>
        </div>
      </Seccion>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6">
        <Kpi titulo="PR-AUC Arequipa" valor={f3(ma.pr_auc)} detalle={`prevalencia ${f3(ma.prevalencia)}`} />
        <Kpi titulo="ROC-AUC Arequipa" valor={f3(ma.roc_auc)} />
        <Kpi titulo="Recall (umbral F2)" valor={f3(ma.recall)} detalle={`precisión ${f3(ma.precision)}`} />
        <Kpi titulo="Obras anticipadas" valor={`${ma.obras_alertadas_antes_del_onset}/${ma.obras_con_onset_en_test}`} detalle={`mediana ${fmtNum(ma.anticipacion_mediana_dias)} días antes`} />
        <Kpi titulo="PR-AUC nacional" valor={f3(mn.pr_auc)} detalle={`prevalencia ${f3(mn.prevalencia)}`} />
        <Kpi titulo="ROC-AUC nacional" valor={f3(mn.roc_auc)} />
      </div>
      {md.metricas.operacion_backtest_arequipa && (
        <Seccion
          titulo="Desempeño operativo en Arequipa (backtest as-of)"
          subtitulo={`Predicciones que la plataforma habría emitido cada mes con modelos reentrenados trimestralmente solo con datos anteriores; ${fmtNum(md.metricas.operacion_backtest_arequipa.filas_observables)} obra-mes con resultado ya observado (prevalencia ${f3(md.metricas.operacion_backtest_arequipa.prevalencia)}).`}
        >
          <table className="tabla w-full max-w-2xl">
            <thead>
              <tr>
                <th>Política</th>
                <th className="text-right">Obras marcadas</th>
                <th className="text-right">Precisión</th>
                <th className="text-right">Recall</th>
              </tr>
            </thead>
            <tbody>
              {(
                [
                  ['Alerta (nivel alto)', md.metricas.operacion_backtest_arequipa.alerta_alto],
                  ['Alerta o vigilancia (alto + medio)', md.metricas.operacion_backtest_arequipa.vigilancia_o_alto],
                  ...(['top_5', 'top_10', 'top_20', 'top_30'] as const).map((k) => [`Revisar el ${k.split('_')[1]}% de mayor riesgo`, { ...(md.metricas.operacion_backtest_arequipa![k] as { precision: number; recall: number }), tasa_marcadas: Number(k.split('_')[1]) / 100 }] as const),
                ] as const
              ).map(([n, v]) => (
                <tr key={n}>
                  <td>{n}</td>
                  <td className="text-right">{f3(v.tasa_marcadas)}</td>
                  <td className="text-right">{f3(v.precision)}</td>
                  <td className="text-right">{f3(v.recall)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Seccion>
      )}
      <Seccion titulo="Matriz de confusión en el test (Arequipa, umbral F2 de validación)">
        <table className="tabla w-full max-w-md text-center">
          <thead>
            <tr>
              <th></th>
              <th className="text-center">Atraso observado</th>
              <th className="text-center">Sin atraso</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="font-medium">Alerta</td>
              <td>{ma.tp}</td>
              <td>{ma.fp}</td>
            </tr>
            <tr>
              <td className="font-medium">Sin alerta</td>
              <td>{ma.fn}</td>
              <td>{ma.tn}</td>
            </tr>
          </tbody>
        </table>
      </Seccion>
      <Seccion
        titulo="Experimento central: Modelo A (estructurado) vs Modelo B (estructurado + documental)"
        subtitulo="Diferencia en el test temporal ciego; IC 95% y p-valor (una cola) por bootstrap de obras completas (1000 remuestreos). LightGBM en ambos casos."
      >
        {c.isLoading ? (
          <Cargando />
        ) : (
          <div className="overflow-x-auto">
            <table className="tabla w-full">
              <thead>
                <tr>
                  <th>H</th>
                  <th>Test</th>
                  <th>Métrica</th>
                  <th>Variante B</th>
                  <th className="text-right">A</th>
                  <th className="text-right">B</th>
                  <th className="text-right">B − A</th>
                  <th className="text-right">IC 95%</th>
                  <th className="text-right">p</th>
                </tr>
              </thead>
              <tbody>
                {(c.data ?? [])
                  .filter((x) => ['B_full', 'B_full_sinproxy', 'B_lex', 'B_stack_tfidf', 'B_emb'].includes(x.variante))
                  .map((x, i) => (
                    <tr key={i} className={x.ic_inf > 0 ? 'bg-green-50' : ''}>
                      <td>{x.horizonte}</td>
                      <td>{x.alcance_test}</td>
                      <td>{x.metrica === 'pr' ? 'PR-AUC' : 'ROC-AUC'}</td>
                      <td title={DESC[x.variante]}>{x.variante}</td>
                      <td className="text-right">{f3(x.a)}</td>
                      <td className="text-right">{f3(x.b)}</td>
                      <td className="text-right font-medium">{f3(x.diferencia)}</td>
                      <td className="text-right text-xs">
                        [{f3(x.ic_inf)}, {f3(x.ic_sup)}]
                      </td>
                      <td className="text-right text-xs">{f3(x.p_valor)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
            <p className="mt-2 text-xs text-slate-500">Filas en verde: el intervalo de confianza de la mejora excluye el cero.</p>
          </div>
        )}
      </Seccion>
      <Seccion
        titulo="Todos los experimentos (objetivo: atraso normativo)"
        accion={
          <select className="entrada" value={scope} onChange={(ev) => setScope(ev.target.value)}>
            <option value="arequipa">Test en Arequipa</option>
            <option value="nacional">Test nacional</option>
          </select>
        }
      >
        {e.isLoading ? (
          <Cargando />
        ) : (
          <div className="max-h-[520px] overflow-auto">
            <table className="tabla w-full">
              <thead className="sticky top-0">
                <tr>
                  <th>H</th>
                  <th>Features</th>
                  <th>Entrenamiento</th>
                  <th>Modelo</th>
                  <th className="text-right">PR-AUC valid</th>
                  <th className="text-right">PR-AUC test</th>
                  <th className="text-right">ROC-AUC test</th>
                  <th className="text-right">Recall</th>
                  <th className="text-right">Precisión</th>
                  <th className="text-right">Prec. top 10%</th>
                </tr>
              </thead>
              <tbody>
                {(e.data ?? []).map((x, i) => (
                  <tr key={i}>
                    <td>{x.horizonte}</td>
                    <td title={DESC[x.conjunto_features]}>{x.conjunto_features}</td>
                    <td>{x.alcance_entrenamiento}</td>
                    <td>{x.modelo}</td>
                    <td className="text-right">{f3(x.metricas.valid_pr_auc)}</td>
                    <td className="text-right font-medium">{f3(x.metricas.pr_auc)}</td>
                    <td className="text-right">{f3(x.metricas.roc_auc)}</td>
                    <td className="text-right">{f3(x.metricas.recall)}</td>
                    <td className="text-right">{f3(x.metricas.precision)}</td>
                    <td className="text-right">{f3(x.metricas.precision_top10)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Seccion>
      <Seccion titulo="Trazabilidad del modelo">
        <div className="grid gap-2 text-xs md:grid-cols-2">
          <div>
            <span className="etiqueta">SHA-256 del artefacto: </span>
            <code className="break-all">{md.sha256}</code>
          </div>
          <div>
            <span className="etiqueta">Variables ({md.features.length}): </span>
            <span className="text-slate-600">{md.features.join(', ')}</span>
          </div>
        </div>
      </Seccion>
    </div>
  )
}
