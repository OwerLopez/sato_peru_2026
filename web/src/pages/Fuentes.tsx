import { useQuery } from '@tanstack/react-query'
import { AlertCircle, CheckCircle2, CircleDot, ExternalLink, Info } from 'lucide-react'
import { useState } from 'react'
import { api, fmtFecha, fmtNum, fmtPct } from '../api'
import { Cargando, CargandoPagina, EncabezadoPagina, ErrorMsg, InfoTip, Kpi, Panel, Seccion } from '../components/ui'

interface Fuentes {
  corte: { fecha_corte: string; generado_en: string; descripcion: string } | null
  archivos: { fuente: string; url: string; ruta: string; bytes: number; sha256: string; last_modified: string; descargado_en: string }[]
  cobertura: Record<string, number>
}
interface Calidad {
  generado_en: string
  chequeos: { seccion: string; clave: string; descripcion: string; valor: number; total: number | null; proporcion: number | null; estado: 'OK' | 'AVISO' | 'INFO' }[]
  frescura: { fuente: string; ultimo_dato: string }[]
  archivos: { total: number; bytes: number; sin_huella: number }
  resumen: Record<'OK' | 'AVISO' | 'INFO', number>
}
interface Sync {
  ultima_sincronizacion: { inicio: string; fin: string | null; estado: string } | null
  proxima_sincronizacion: string
  fuentes: { fuente: string; estado: string; ms: number }[] | null
  verificado_hace_s: number
}

const LIMITES = [
  'Los asientos del cuaderno de obra digital solo están publicados desde junio de 2024; se analizan las obras cuyo asiento N° 1 está dentro de esa ventana (historia completa).',
  'Los cuadernos no incluyen el código único de inversión (CUI): se enlazaron por el código citado en el nombre de la obra y por similitud de texto calibrada (precisión de 99,1 % en 10 075 pares con CUI explícito).',
  'INFOBRAS publica la situación actual de cada obra; sus campos cambiantes (avance, paralización, fin real) no se usan para predecir, solo los fijados al inicio (plazo y monto originales).',
  'El presupuesto modificado (PIM) del año en curso en SIAF no está fechado; solo se usan el gasto devengado mensual (con un mes de rezago) y el presupuesto inicial (PIA).',
  'El modelo de alerta a 60 días cubre contratos con cuaderno de obra digital; las demás modalidades se cubren con los modelos de la cartera INFOBRAS (riesgo al término).',
  'El conjunto de datos abiertos de INFOBRAS tiene registros hasta marzo de 2026; las obras en ejecución sin registros en los 12 meses previos no se evalúan.',
  'Las fuentes se regeneran periódicamente y pueden cambiar sin aviso; por eso cada archivo descargado se registra con su huella SHA-256.',
]

function IconoEstado({ e }: { e: 'OK' | 'AVISO' | 'INFO' }) {
  if (e === 'OK') return <CheckCircle2 className="size-4 text-bajo" aria-label="Sin hallazgos" />
  if (e === 'AVISO') return <AlertCircle className="size-4 text-medio" aria-label="Hallazgo documentado" />
  return <Info className="size-4 text-slate-400" aria-label="Dato descriptivo" />
}

function CalidadDatos() {
  const q = useQuery({ queryKey: ['calidad'], queryFn: () => api<Calidad | null>('/sistema/calidad') })
  if (q.isLoading) return <Cargando />
  if (q.error) return <ErrorMsg error={q.error} />
  if (!q.data) return null
  const c = q.data
  const secciones = [...new Set(c.chequeos.map((x) => x.seccion))]
  return (
    <Seccion
      titulo="Auditoría de calidad de los datos"
      subtitulo={`${c.chequeos.length} verificaciones automáticas sobre la base cargada (${fmtFecha(c.generado_en)}). Los hallazgos se informan tal como están en las fuentes oficiales; ninguno se corrige ni se oculta.`}
      accion={
        <div className="flex gap-3 text-xs text-slate-600">
          <span className="inline-flex items-center gap-1">
            <CheckCircle2 className="size-3.5 text-bajo" /> {c.resumen.OK} sin hallazgos
          </span>
          <span className="inline-flex items-center gap-1">
            <AlertCircle className="size-3.5 text-medio" /> {c.resumen.AVISO} con hallazgos
          </span>
          <span className="inline-flex items-center gap-1">
            <Info className="size-3.5 text-slate-400" /> {c.resumen.INFO} descriptivos
          </span>
        </div>
      }
      sinRelleno
    >
      <div className="grid divide-y divide-slate-100 lg:grid-cols-2 lg:divide-x lg:divide-y-0">
        {[secciones.slice(0, Math.ceil(secciones.length / 2)), secciones.slice(Math.ceil(secciones.length / 2))].map((grupo, gi) => (
          <div key={gi} className="divide-y divide-slate-100">
            {grupo.map((s) => (
              <div key={s} className="px-4 py-3">
                <div className="etiqueta mb-2">{s}</div>
                <ul className="space-y-2">
                  {c.chequeos
                    .filter((x) => x.seccion === s)
                    .map((x) => (
                      <li key={x.clave} className="flex items-start gap-2 text-sm">
                        <span className="mt-0.5">
                          <IconoEstado e={x.estado} />
                        </span>
                        <span className="flex-1 text-slate-700">{x.descripcion}</span>
                        <span className="num shrink-0 text-right text-slate-900">
                          {fmtNum(x.valor)}
                          {x.total !== null && x.total > 0 && x.valor > 0 && <span className="block text-[11px] text-slate-500">{fmtPct(x.proporcion, x.proporcion! < 0.01 && x.valor > 0 ? 2 : 1)} de {fmtNum(x.total)}</span>}
                        </span>
                      </li>
                    ))}
                </ul>
              </div>
            ))}
          </div>
        ))}
      </div>
      <div className="border-t border-slate-100 px-4 py-3">
        <div className="etiqueta mb-2">Dato más reciente de cada fuente</div>
        <div className="grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-5">
          {c.frescura.map((f) => (
            <div key={f.fuente} className="rounded-lg bg-slate-50 px-3 py-2">
              <div className="text-xs text-slate-500">{f.fuente}</div>
              <div className="num font-medium text-slate-900">{f.ultimo_dato === 'None' ? '—' : fmtFecha(f.ultimo_dato)}</div>
            </div>
          ))}
        </div>
      </div>
    </Seccion>
  )
}

function EstadoSync() {
  const q = useQuery({ queryKey: ['sync'], queryFn: () => api<Sync>('/sistema/sincronizacion'), staleTime: 60_000 })
  return (
    <Seccion titulo="Disponibilidad de las fuentes y sincronización" subtitulo={q.data ? `Portales verificados en vivo hace ${fmtNum(q.data.verificado_hace_s)} s.` : 'Verificando portales oficiales…'}>
      {q.isLoading ? (
        <Cargando filas={4} />
      ) : q.error || !q.data ? (
        <ErrorMsg error={q.error ?? 'Sin datos'} />
      ) : (
        <div className="space-y-4">
          <ul className="space-y-2">
            {(q.data.fuentes ?? []).map((f) => (
              <li key={f.fuente} className="flex items-center gap-2 text-sm">
                <CircleDot className={`size-4 ${f.estado === 'EN_LINEA' ? 'text-bajo' : 'text-alto'}`} />
                <span className="flex-1 text-slate-700">{f.fuente}</span>
                <span className={`text-xs font-medium ${f.estado === 'EN_LINEA' ? 'text-bajo' : 'text-alto'}`}>{f.estado === 'EN_LINEA' ? 'En línea' : f.estado.replace('_', ' ').toLowerCase()}</span>
                <span className="num w-16 text-right text-xs text-slate-500">{fmtNum(f.ms)} ms</span>
              </li>
            ))}
          </ul>
          <dl className="grid grid-cols-2 gap-3 border-t border-slate-100 pt-3 text-sm">
            <div>
              <dt className="text-xs text-slate-500">Última sincronización automática</dt>
              <dd className="mt-0.5">{q.data.ultima_sincronizacion ? `${q.data.ultima_sincronizacion.estado.toLowerCase()} · ${fmtFecha(q.data.ultima_sincronizacion.inicio)}` : 'Aún sin ejecuciones del proceso programado'}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">Próxima actualización programada</dt>
              <dd className="mt-0.5">{fmtFecha(q.data.proxima_sincronizacion)}</dd>
            </div>
          </dl>
        </div>
      )}
    </Seccion>
  )
}

export default function FuentesPage() {
  const q = useQuery({ queryKey: ['fuentes'], queryFn: () => api<Fuentes>('/fuentes') })
  const [linaje, setLinaje] = useState(false)
  if (q.isLoading) return <CargandoPagina />
  if (q.error) return <ErrorMsg error={q.error} reintentar={() => q.refetch()} />
  const d = q.data!
  const c = d.cobertura
  const bytes = d.archivos.reduce((s, a) => s + (a.bytes ?? 0), 0)
  return (
    <div className="space-y-5">
      <EncabezadoPagina
        titulo="Datos y fuentes"
        descripcion={`Todos los datos provienen de fuentes oficiales abiertas del Estado peruano, sin datos simulados. Corte de datos: ${fmtFecha(d.corte?.fecha_corte)}.`}
        acciones={
          <button className="btn" onClick={() => setLinaje(true)}>
            Ver los {fmtNum(d.archivos.length)} archivos oficiales
          </button>
        }
      />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi titulo="Obras con cuaderno digital" ayuda="cuaderno" valor={fmtNum(c.obras)} detalle={`${fmtNum(c.obras_historia_completa)} con historia completa desde el primer asiento.`} />
        <Kpi titulo="Enlazadas a una inversión (CUI)" ayuda="cui" valor={fmtNum(c.obras_con_cui)} detalle={`${fmtPct(c.obras_con_cui / c.obras)} de las obras; permite unir Invierte.pe y SIAF.`} />
        <Kpi titulo="Enlazadas a INFOBRAS" valor={fmtNum(c.obras_con_infobras)} detalle={`${fmtNum(c.obras_con_contrato_seace)} con contrato publicado en SEACE.`} />
        <Kpi titulo="Inversiones con gasto mensual (SIAF)" ayuda="devengado" valor={fmtNum(c.inversiones_con_siaf)} detalle={`De obras con cuaderno digital o de la cartera INFOBRAS; además, ${fmtNum(c.registros_contraloria)} registros de obras paralizadas.`} />
      </div>
      <CalidadDatos />
      <div className="grid gap-5 lg:grid-cols-2">
        <EstadoSync />
        <Seccion titulo="Limitaciones conocidas" subtitulo="Condiciones de las fuentes que acotan lo que el sistema puede afirmar.">
          <ul className="space-y-2 text-sm leading-relaxed text-slate-700">
            {LIMITES.map((l) => (
              <li key={l} className="flex gap-2">
                <span className="mt-2 size-1.5 shrink-0 rounded-full bg-slate-400" aria-hidden />
                {l}
              </li>
            ))}
          </ul>
        </Seccion>
      </div>
      <Panel abierto={linaje} onClose={() => setLinaje(false)} titulo="Linaje de los datos" subtitulo={`${fmtNum(d.archivos.length)} archivos oficiales · ${fmtNum(bytes / 1e9, 2)} GB en total`} ancho="max-w-4xl">
        <p className="mb-3 flex items-center gap-1 text-sm text-slate-600">
          URL de origen, tamaño, fecha de modificación declarada por el servidor, fecha de descarga y huella SHA-256 de cada archivo.
          <InfoTip texto="La huella SHA-256 identifica el contenido exacto del archivo: si la fuente cambia, la huella cambia." />
        </p>
        <table className="tabla">
          <thead>
            <tr>
              <th>Fuente y archivo</th>
              <th className="text-right">Tamaño</th>
              <th>Descargado</th>
              <th>SHA-256</th>
            </tr>
          </thead>
          <tbody>
            {d.archivos.map((a) => (
              <tr key={a.ruta}>
                <td className="text-xs">
                  <div className="text-slate-500">{a.fuente}</div>
                  <a href={a.url} target="_blank" rel="noopener noreferrer" className="enlace inline-flex items-center gap-1 break-all">
                    {a.ruta} <ExternalLink className="size-3 shrink-0" />
                  </a>
                </td>
                <td className="num text-right text-xs whitespace-nowrap">{fmtNum(a.bytes / 1e6, 1)} MB</td>
                <td className="text-xs whitespace-nowrap">{fmtFecha(a.descargado_en)}</td>
                <td className="font-mono text-[10px] text-slate-500">{a.sha256?.slice(0, 16)}…</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  )
}
