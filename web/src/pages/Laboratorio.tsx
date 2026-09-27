import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, fmtFecha, fmtNum, fmtPct, qs, type Nivel } from '../api'
import { useAmbito } from '../ambito'
import { Cargando, ErrorMsg, Kpi, NivelBadge, Paginacion, Seccion } from '../components/ui'
import ModeloPage from './Modelo'

interface CardCartera {
  obs_end: string
  umbrales: Record<string, { alto: number; medio: number; tasa_base_test: number; periodo_test_desde: string; tasa_por_nivel_test: Record<string, { filas: number; tasa_retraso_observada: number }> }>
  metricas_test: Record<string, Record<string, { arequipa: Record<string, number>; nacional: Record<string, number> }>>
  periodos: Record<string, Record<string, (string | number)[]>>
}
const f3 = (x?: number) => (x === undefined || x === null || Number.isNaN(x) ? '—' : x.toFixed(3))

function ModelosCartera() {
  const q = useQuery({ queryKey: ['modelo-cartera'], queryFn: () => api<CardCartera>('/modelo/cartera') })
  if (q.isLoading) return <Cargando />
  if (q.error || !q.data) return <ErrorMsg error={q.error ?? 'sin datos'} />
  const c = q.data
  const ini = c.metricas_test.inicio
  const seg = c.metricas_test.seguimiento
  return (
    <div className="space-y-5">
      <Seccion titulo="Definición">
        <p className="text-sm">
          <b>Retraso significativo al término</b>: la obra culmina después de su fecha programada original más el 30% del plazo original. La etiqueta solo se
          asigna con evidencia (fecha real de fin, o registros de avance posteriores al límite); los registros abandonados se excluyen. Modelo <b>al inicio</b>: solo
          información conocida al iniciar la obra, incluido el historial de retrasos de la entidad, el contratista y la provincia con resultados conocidos antes del
          inicio. Modelo de <b>seguimiento</b>: además, avance del plazo y ejecución financiera mensual del SIAF (con un mes de rezago).
        </p>
      </Seccion>
      {(['inicio', 'seguimiento'] as const).map((t) => {
        const m = t === 'inicio' ? ini.lgbm : seg.seguimiento_lgbm
        const base = t === 'seguimiento' ? seg.exante_lgbm : ini.regla
        const u = c.umbrales[t]
        const per = c.periodos[t]
        return (
          <Seccion
            key={t}
            titulo={t === 'inicio' ? 'Modelo al inicio de la obra (LightGBM)' : 'Modelo de seguimiento mensual con SIAF (LightGBM)'}
            subtitulo={`Test temporal ciego: ${per.test?.[0]} a ${per.test?.[1]} (${fmtNum(Number(per.test?.[2]))} ${t === 'inicio' ? 'obras' : 'obra-mes'}); entrenamiento solo con resultados conocidos antes del test.`}
          >
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6">
              <Kpi titulo="ROC-AUC Arequipa" valor={f3(m.arequipa.roc_auc)} detalle={`${t === 'inicio' ? 'regla histórica de la entidad' : 'solo al inicio'}: ${f3(base.arequipa.roc_auc)}`} />
              <Kpi titulo="PR-AUC Arequipa" valor={f3(m.arequipa.pr_auc)} detalle={`prevalencia ${f3(m.arequipa.prevalencia)}`} />
              <Kpi titulo="ROC-AUC nacional" valor={f3(m.nacional.roc_auc)} detalle={`${t === 'inicio' ? 'regla' : 'solo al inicio'}: ${f3(base.nacional.roc_auc)}`} />
              <Kpi titulo="PR-AUC nacional" valor={f3(m.nacional.pr_auc)} detalle={`prevalencia ${f3(m.nacional.prevalencia)}`} />
              <Kpi titulo="Precisión (umbral F1)" valor={f3(m.nacional.precision)} detalle={`recall ${f3(m.nacional.recall)}`} />
              <Kpi titulo="Obras de test Arequipa" valor={fmtNum(m.arequipa.n)} />
            </div>
            <table className="tabla mt-4 w-full max-w-xl">
              <thead>
                <tr>
                  <th>Nivel</th>
                  <th className="text-right">Filas evaluadas</th>
                  <th className="text-right">Terminaron con retraso significativo</th>
                </tr>
              </thead>
              <tbody>
                {(['ALTO', 'MEDIO', 'BAJO'] as Nivel[]).map((n) => (
                  <tr key={n}>
                    <td>
                      <NivelBadge nivel={n} />
                    </td>
                    <td className="text-right">{fmtNum(u.tasa_por_nivel_test[n]?.filas)}</td>
                    <td className="text-right">{fmtPct(u.tasa_por_nivel_test[n]?.tasa_retraso_observada)}</td>
                  </tr>
                ))}
                <tr>
                  <td>Tasa base</td>
                  <td></td>
                  <td className="text-right">{fmtPct(u.tasa_base_test)}</td>
                </tr>
              </tbody>
            </table>
            <p className="mt-2 text-xs text-slate-500">
              Niveles definidos con predicciones fuera de tiempo anteriores al {fmtFecha(u.periodo_test_desde)} (ALTO = 20% de mayor riesgo, MEDIO = siguiente 30%), y
              evaluados después de esa fecha.
            </p>
          </Seccion>
        )
      })}
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
  estado_operativo: string
}

function Historicas() {
  const { departamento } = useAmbito()
  const [estado, setEstado] = useState('FINALIZADA')
  const [pagina, setPagina] = useState(1)
  const p = { departamento, estado, pagina, tamanio: 20, orden: 'reciente' }
  const q = useQuery({ queryKey: ['hist', p], queryFn: () => api<{ total: number; items: Hist[] }>(`/cartera${qs(p)}`) })
  return (
    <Seccion
      titulo="Obras con resultado conocido: estimación vs. realidad"
      subtitulo="Estimación calculada solo con información anterior (as-of). Permite auditar aciertos y errores del modelo obra por obra."
      accion={
        <select aria-label="Estado de las obras"
          className="entrada"
          value={estado}
          onChange={(e) => {
            setEstado(e.target.value)
            setPagina(1)
          }}
        >
          <option value="FINALIZADA">Finalizadas</option>
          <option value="CONSUMADO">Con retraso ya consumado</option>
        </select>
      }
    >
      {q.isLoading ? (
        <Cargando />
      ) : (
        <>
          <table className="tabla w-full">
            <thead>
              <tr>
                <th>Obra</th>
                <th>Inicio</th>
                <th>Estimación</th>
                <th>Resultado observado</th>
              </tr>
            </thead>
            <tbody>
              {q.data?.items.map((o) => (
                <tr key={o.codigo_infobras}>
                  <td className="max-w-xl">
                    <Link to={`/cartera/${o.codigo_infobras}`} className="text-marca-700 hover:underline">
                      {o.nombre.slice(0, 140)}
                    </Link>
                    <div className="text-xs text-slate-500">
                      {o.provincia}, {o.departamento}
                    </div>
                  </td>
                  <td className="text-xs">{fmtFecha(o.fecha_inicio)}</td>
                  <td>
                    <NivelBadge nivel={o.nivel} score={o.score} />
                  </td>
                  <td className="text-xs">
                    {o.retraso_significativo === null ? '—' : o.retraso_significativo ? <span className="text-alto">retraso significativo</span> : <span className="text-bajo">sin retraso significativo</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <Paginacion pagina={pagina} total={q.data?.total ?? 0} tamanio={20} onChange={setPagina} />
        </>
      )}
    </Seccion>
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

function TablaSectores({ titulo, texto, b }: { titulo: string; texto: string; b: BloqueSector }) {
  const max = Math.max(...b.sectores.map((x) => x.roc_auc), b.global.roc_auc)
  return (
    <Seccion titulo={titulo} subtitulo={texto}>
      <div className="overflow-x-auto">
        <table className="tabla w-full">
          <thead>
            <tr>
              <th>Sector / tipo de obra</th>
              <th className="text-right">Observaciones</th>
              <th className="text-right">Con evento</th>
              <th className="text-right">Prevalencia</th>
              <th>ROC-AUC (IC 95 %)</th>
              <th className="text-right">PR-AUC</th>
              <th className="text-right">Concentración en el 10 % de mayor riesgo</th>
            </tr>
          </thead>
          <tbody>
            {[{ sector: 'TODOS (global)', ...b.global }, ...b.sectores].map((x) => (
              <tr key={x.sector} className={x.sector.startsWith('TODOS') ? 'font-semibold' : ''}>
                <td>{NOMBRE_SECTOR[x.sector] ?? x.sector}</td>
                <td className="text-right">{fmtNum(x.filas)}</td>
                <td className="text-right">{fmtNum(x.positivos)}</td>
                <td className="text-right">{fmtPct(x.prevalencia)}</td>
                <td>
                  <div className="flex items-center gap-2">
                    <div className="h-2 w-28 rounded bg-slate-100">
                      <div className="h-2 rounded bg-marca-600" style={{ width: `${(100 * (x.roc_auc - 0.5)) / (max - 0.5)}%` }} />
                    </div>
                    <span>
                      {f3(x.roc_auc)} <span className="text-xs text-slate-500">[{f3(x.roc_ic95[0])}; {f3(x.roc_ic95[1])}]</span>
                    </span>
                  </div>
                </td>
                <td className="text-right">{f3(x.pr_auc)}</td>
                <td className="text-right">{x.lift_top10.toFixed(1)} veces la prevalencia</td>
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
  if (!q.data) return <ErrorMsg error="Evaluación por sector no disponible (ejecutar python -m sato.models.por_sector)." />
  const d = q.data
  return (
    <div className="space-y-5">
      <p className="text-sm text-slate-600">
        ¿En qué sectores funciona la predicción? Cada modelo se evaluó, sin reentrenar, sobre su periodo de prueba temporal separando las obras por sector. Se
        muestran los grupos con al menos 30 obras con y sin evento. La concentración indica cuántas veces más casos hay entre el 10 % de obras que el modelo
        ordena primero que en una selección al azar.
      </p>
      <TablaSectores
        titulo="Alerta a 60 días (cuaderno de obra digital)"
        texto="Atraso normativo (regla del 80 %) en los 60 días siguientes; prueba de diciembre de 2025 a junio de 2026."
        b={d.alerta_60d}
      />
      <TablaSectores
        titulo="Cartera INFOBRAS: seguimiento mensual con SIAF"
        texto="Retraso significativo al término (más de 30 % del plazo); cortes mensuales de 2024 y 2025, todas las modalidades."
        b={d.cartera_seguimiento}
      />
      <TablaSectores
        titulo="Cartera INFOBRAS: estimación al inicio de la obra"
        texto="Retraso significativo al término; obras iniciadas entre enero de 2022 y junio de 2024."
        b={d.cartera_inicio}
      />
    </div>
  )
}

export default function Laboratorio() {
  const [tab, setTab] = useState<'cuaderno' | 'cartera' | 'sectores' | 'historicas'>('cuaderno')
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-marca-900">Laboratorio de validación histórica</h1>
        <p className="text-sm text-slate-600">
          Evidencia de que las predicciones funcionan: evaluación temporal ciega (entrenar con el pasado, probar en el futuro), comparación científica de modelos y
          contraste obra por obra entre lo estimado y lo ocurrido.
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <button className={tab === 'cuaderno' ? 'btn-primario' : 'btn'} onClick={() => setTab('cuaderno')}>
          Modelo de alerta a 60 días (cuaderno digital)
        </button>
        <button className={tab === 'cartera' ? 'btn-primario' : 'btn'} onClick={() => setTab('cartera')}>
          Modelos de la cartera INFOBRAS
        </button>
        <button className={tab === 'sectores' ? 'btn-primario' : 'btn'} onClick={() => setTab('sectores')}>
          Desempeño por sector
        </button>
        <button className={tab === 'historicas' ? 'btn-primario' : 'btn'} onClick={() => setTab('historicas')}>
          Obras históricas: estimado vs. real
        </button>
      </div>
      {tab === 'cuaderno' ? <ModeloPage /> : tab === 'cartera' ? <ModelosCartera /> : tab === 'sectores' ? <Sectores /> : <Historicas />}
    </div>
  )
}
