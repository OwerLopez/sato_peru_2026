// Detalle técnico del modelo de alerta a 60 días: experimentos, comparación A/B y trazabilidad del artefacto.
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api, fmtDec, fmtFecha, fmtNum, qs } from '../api'
import { Cargando, ErrorMsg, InfoTip, Seccion, Segmentado } from '../components/ui'

export interface Metricas {
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
export interface Politica {
  tasa_marcadas?: number
  precision: number
  recall: number
}
export interface Backtest {
  filas_observables: number
  prevalencia: number
  alerta_alto: Politica
  vigilancia_o_alto: Politica
  top_5?: Politica
  top_10?: Politica
  top_20?: Politica
  top_30?: Politica
}
export interface Modelo {
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
    operacion_backtest_arequipa?: Backtest
    operacion_backtest_nacional?: Backtest
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
}
interface Exp {
  horizonte: number
  conjunto_features: string
  alcance_entrenamiento: string
  modelo: string
  metricas: Metricas & { valid_pr_auc: number }
}

const f3 = (x?: number | null) => fmtDec(x, 3)
const DESC: Record<string, string> = {
  A: 'Datos estructurados (tipos de asiento, actividad, contrato, SIAF, F12B, historial)',
  A_sin_ib: 'A sin atributos INFOBRAS',
  A_asientos: 'Solo metadatos de los asientos',
  B_lex: 'A + léxico de causas de atraso',
  B_lex_sinproxy: 'A + léxico sin menciones de la regla del 80 %',
  B_ie: 'A + avances declarados en los asientos',
  B_lsa: 'A + LSA (TF-IDF + SVD)',
  B_emb: 'A + embeddings Sentence-BERT',
  B_stack_tfidf: 'A + índice de texto TF-IDF',
  B_stack_emb: 'A + índice de embeddings',
  B_full: 'A + todo el componente de texto',
  B_full_sinproxy: 'B_full sin léxico de la regla del 80 % ni extracción',
}

export function TablaPoliticas({ titulo, b }: { titulo: string; b: Backtest }) {
  const filas: [string, Politica][] = [
    ['Revisar las obras en riesgo alto', b.alerta_alto],
    ['Revisar riesgo alto y medio', b.vigilancia_o_alto],
    ...(['top_5', 'top_10', 'top_20', 'top_30'] as const)
      .filter((k) => b[k])
      .map((k): [string, Politica] => [`Revisar el ${k.split('_')[1]} % de mayor riesgo`, { ...b[k]!, tasa_marcadas: Number(k.split('_')[1]) / 100 }]),
  ]
  return (
    <div>
      <div className="mb-2 text-sm font-medium text-slate-800">{titulo}</div>
      <div className="overflow-x-auto">
        <table className="tabla">
          <thead>
            <tr>
              <th>Estrategia de revisión mensual</th>
              <th className="text-right">Obras revisadas</th>
              <th className="text-right">Aciertos</th>
              <th className="text-right">Atrasos encontrados</th>
            </tr>
          </thead>
          <tbody>
            {filas.map(([n, v]) => (
              <tr key={n}>
                <td>{n}</td>
                <td className="num text-right">{fmtNum(100 * (v.tasa_marcadas ?? 0), 1)} %</td>
                <td className="num text-right">{fmtNum(100 * v.precision, 1)} %</td>
                <td className="num text-right">{fmtNum(100 * v.recall, 1)} %</td>
              </tr>
            ))}
            <tr className="text-slate-500">
              <td>Revisar al azar (referencia)</td>
              <td className="num text-right">—</td>
              <td className="num text-right">{fmtNum(100 * b.prevalencia, 1)} %</td>
              <td className="num text-right">—</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p className="mt-1.5 text-xs text-slate-500">
        {fmtNum(b.filas_observables)} obras-mes con resultado conocido. «Aciertos»: proporción de obras revisadas que tuvieron el atraso formal en 60 días. «Atrasos encontrados»: proporción de todos los
        atrasos que habrían estado entre las obras revisadas.
      </p>
    </div>
  )
}

export function DetalleTecnico() {
  const m = useQuery({ queryKey: ['modelo'], queryFn: () => api<Modelo>('/modelo') })
  const c = useQuery({ queryKey: ['comp'], queryFn: () => api<Comp[]>('/investigacion/comparacion?objetivo=atraso') })
  const [scope, setScope] = useState<'nacional' | 'arequipa'>('nacional')
  const e = useQuery({ queryKey: ['exp', scope], queryFn: () => api<Exp[]>(`/investigacion/experimentos${qs({ objetivo: 'atraso', alcance_test: scope })}`) })
  if (m.isLoading) return <Cargando />
  if (m.error) return <ErrorMsg error={m.error} />
  const md = m.data!
  const per = md.metricas.periodos
  const mn = md.metricas.nacional
  return (
    <div className="space-y-5">
      <Seccion titulo="Diseño de la evaluación">
        <dl className="grid gap-4 text-sm md:grid-cols-3">
          <div>
            <dt className="etiqueta">Evento que se predice</dt>
            <dd className="mt-1 leading-relaxed text-slate-700">
              Primer asiento del cuaderno de obra digital de «Valorización acumulada menor al 80 % de lo programado» o «Calendario acelerado de obra» (DS 344-2018-EF, art. 203; DS
              009-2025-EF, art. 207), dentro de los {md.horizonte_dias} días siguientes al corte.
            </dd>
          </div>
          <div>
            <dt className="etiqueta">Unidad y tiempo</dt>
            <dd className="mt-1 leading-relaxed text-slate-700">
              Obra-mes. En cada fin de mes solo se usa información fechada hasta ese día (asientos, gasto SIAF del mes anterior, seguimiento F12B e historial de actores).
            </dd>
          </div>
          <div>
            <dt className="etiqueta">Partición temporal</dt>
            <dd className="mt-1 leading-relaxed text-slate-700">
              Entrenamiento {fmtFecha(per?.train?.[0])} – {fmtFecha(per?.train?.[1])}; validación {fmtFecha(per?.valid?.[0])} – {fmtFecha(per?.valid?.[1])}; prueba {fmtFecha(per?.test?.[0])} –{' '}
              {fmtFecha(per?.test?.[1])}, con {md.horizonte_dias} días de separación. Umbrales e hiperparámetros elegidos solo en validación.
            </dd>
          </div>
        </dl>
      </Seccion>
      <Seccion titulo="Matriz de confusión en la prueba nacional" subtitulo="Con el umbral de riesgo alto elegido en validación.">
        <div className="flex flex-wrap gap-6">
          <table className="tabla max-w-md text-center">
            <thead>
              <tr>
                <th><span className="sr-only">Estimación del modelo</span></th>
                <th className="text-center">Hubo atraso formal</th>
                <th className="text-center">No hubo</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row" className="text-left font-medium normal-case tracking-normal text-sm text-slate-800 bg-transparent">Alerta emitida</th>
                <td className="num">{fmtNum(mn.tp)}</td>
                <td className="num">{fmtNum(mn.fp)}</td>
              </tr>
              <tr>
                <th scope="row" className="text-left font-medium normal-case tracking-normal text-sm text-slate-800 bg-transparent">Sin alerta</th>
                <td className="num">{fmtNum(mn.fn)}</td>
                <td className="num">{fmtNum(mn.tn)}</td>
              </tr>
            </tbody>
          </table>
          <dl className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
            <dt className="flex items-center gap-1 text-slate-500">
              ROC-AUC <InfoTip termino="roc_auc" />
            </dt>
            <dd className="num font-medium">{f3(mn.roc_auc)}</dd>
            <dt className="flex items-center gap-1 text-slate-500">
              PR-AUC <InfoTip termino="pr_auc" />
            </dt>
            <dd className="num font-medium">
              {f3(mn.pr_auc)} <span className="text-xs text-slate-500">(azar {f3(mn.prevalencia)})</span>
            </dd>
            <dt className="text-slate-500">Precisión</dt>
            <dd className="num font-medium">{f3(mn.precision)}</dd>
            <dt className="text-slate-500">Sensibilidad (recall)</dt>
            <dd className="num font-medium">{f3(mn.recall)}</dd>
          </dl>
        </div>
      </Seccion>
      <Seccion
        titulo="Experimento central: ¿aporta el texto de los asientos?"
        ayuda="intervalo"
        subtitulo="Modelo A (solo datos estructurados) frente a B (además, el texto de los asientos). Diferencia en la prueba temporal con IC 95 % y p-valor por bootstrap de obras (1 000 remuestreos)."
      >
        {c.isLoading ? (
          <Cargando />
        ) : (
          <div className="overflow-x-auto">
            <table className="tabla min-w-[760px]">
              <thead>
                <tr>
                  <th>Horizonte</th>
                  <th>Prueba</th>
                  <th>Métrica</th>
                  <th>Variante B</th>
                  <th className="text-right">A</th>
                  <th className="text-right">B</th>
                  <th className="text-right">B − A</th>
                  <th className="text-right">IC 95 %</th>
                  <th className="text-right">p</th>
                </tr>
              </thead>
              <tbody>
                {(c.data ?? [])
                  .filter((x) => ['B_full', 'B_full_sinproxy', 'B_lex', 'B_stack_tfidf', 'B_emb'].includes(x.variante))
                  .map((x, i) => (
                    <tr key={i} className={x.ic_inf > 0 ? 'bg-bajo-suave/60' : ''}>
                      <td className="num">{x.horizonte} días</td>
                      <td>{x.alcance_test === 'nacional' ? 'Nacional' : 'Arequipa'}</td>
                      <td>{x.metrica === 'pr' ? 'PR-AUC' : 'ROC-AUC'}</td>
                      <td title={DESC[x.variante]}>{DESC[x.variante] ?? x.variante}</td>
                      <td className="num text-right">{f3(x.a)}</td>
                      <td className="num text-right">{f3(x.b)}</td>
                      <td className="num text-right font-medium">{f3(x.diferencia)}</td>
                      <td className="num text-right text-xs">
                        [{f3(x.ic_inf)}; {f3(x.ic_sup)}]
                      </td>
                      <td className="num text-right text-xs">{f3(x.p_valor)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
            <p className="mt-2 text-xs text-slate-500">Filas resaltadas: el intervalo de confianza de la mejora excluye el cero.</p>
          </div>
        )}
      </Seccion>
      <Seccion
        titulo="Todos los experimentos"
        sinRelleno
        accion={
          <Segmentado
            etiqueta="Ámbito de la prueba"
            valor={scope}
            onChange={setScope}
            opciones={[
              { v: 'nacional', l: 'Prueba nacional' },
              { v: 'arequipa', l: 'Prueba en Arequipa' },
            ]}
          />
        }
      >
        {e.isLoading ? (
          <div className="p-4">
            <Cargando />
          </div>
        ) : (
          <div className="max-h-[520px] overflow-auto">
            <table className="tabla min-w-[900px]">
              <thead>
                <tr>
                  <th>Horizonte</th>
                  <th>Variables</th>
                  <th>Entrenamiento</th>
                  <th>Algoritmo</th>
                  <th className="text-right">PR-AUC valid.</th>
                  <th className="text-right">PR-AUC prueba</th>
                  <th className="text-right">ROC-AUC prueba</th>
                  <th className="text-right">Sensibilidad</th>
                  <th className="text-right">Precisión</th>
                  <th className="text-right">Precisión 10 % superior</th>
                </tr>
              </thead>
              <tbody>
                {(e.data ?? []).map((x, i) => (
                  <tr key={i}>
                    <td className="num">{x.horizonte}</td>
                    <td title={DESC[x.conjunto_features]}>{x.conjunto_features}</td>
                    <td>{x.alcance_entrenamiento}</td>
                    <td>{x.modelo}</td>
                    <td className="num text-right">{f3(x.metricas.valid_pr_auc)}</td>
                    <td className="num text-right font-medium">{f3(x.metricas.pr_auc)}</td>
                    <td className="num text-right">{f3(x.metricas.roc_auc)}</td>
                    <td className="num text-right">{f3(x.metricas.recall)}</td>
                    <td className="num text-right">{f3(x.metricas.precision)}</td>
                    <td className="num text-right">{f3(x.metricas.precision_top10)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Seccion>
      <Seccion titulo="Trazabilidad del modelo en producción">
        <dl className="grid gap-3 text-sm md:grid-cols-2">
          <div>
            <dt className="etiqueta">Versión y algoritmo</dt>
            <dd className="mt-1">
              {md.version} · {md.algoritmo} · entrenado con cortes hasta {fmtFecha(md.entrenado_hasta)}
            </dd>
          </div>
          <div>
            <dt className="etiqueta">Huella SHA-256 del artefacto</dt>
            <dd className="mt-1 font-mono text-xs break-all text-slate-600">{md.sha256}</dd>
          </div>
          <div className="md:col-span-2">
            <dt className="etiqueta">Variables del modelo ({md.features.length})</dt>
            <dd className="mt-1 font-mono text-xs leading-relaxed text-slate-600">{md.features.join(', ')}</dd>
          </div>
        </dl>
      </Seccion>
    </div>
  )
}
