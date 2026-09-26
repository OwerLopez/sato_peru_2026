import { useQuery } from '@tanstack/react-query'
import { api, fmtFecha, fmtNum } from '../api'
import { Cargando, ErrorMsg, Kpi, Seccion } from '../components/ui'

interface Fuentes {
  corte: { fecha_corte: string; generado_en: string; descripcion: string } | null
  archivos: { fuente: string; url: string; ruta: string; bytes: number; sha256: string; last_modified: string; descargado_en: string }[]
  cobertura: Record<string, number>
}

const LIMITES = [
  'Los asientos del cuaderno de obra digital solo están publicados desde junio de 2024; se analizan únicamente obras cuyo asiento N° 1 está dentro de esa ventana (historia completa).',
  'Los cuadernos no contienen el CUI: se enlazaron por regex del código citado en el nombre y por similitud TF-IDF calibrada (precisión 99,1% medida sobre 10 075 pares con CUI explícito).',
  'INFOBRAS publica una foto actual por obra; sus campos variables (avance, paralización, fin real) no se usan para predecir, solo los fijados al inicio (plazo y monto originales).',
  'El PIM del año en curso en SIAF no está fechado; solo se usan el devengado mensual (con un mes de rezago) y el PIA.',
  'El modelo de alerta a 60 días cubre contratos con cuaderno de obra digital; las demás modalidades se cubren con los modelos de la cartera INFOBRAS (riesgo al término).',
  'El dataset abierto de INFOBRAS recibe registros hasta marzo de 2026; las obras en ejecución sin registros en los 12 meses previos se marcan como desactualizadas y no se evalúan.',
  'Las fuentes se regeneran periódicamente (p.ej. un archivo CONOSCE de contratos cambió de 10 988 a 9 666 filas el 25/09/2026); por ello cada archivo se registra con su SHA-256.',
]

interface Sync {
  corte: { fecha_corte: string } | null
  ultima_sincronizacion: { inicio: string; fin: string | null; estado: string; corte_datos: string | null } | null
  proxima_sincronizacion: string
  fuentes: { fuente: string; estado: string; ms: number }[] | null
  verificado_hace_s: number
}

function EstadoSync() {
  const q = useQuery({ queryKey: ['sync'], queryFn: () => api<Sync>('/sistema/sincronizacion'), staleTime: 60_000 })
  if (q.isLoading) return <Cargando texto="Verificando fuentes oficiales…" />
  if (q.error || !q.data) return <ErrorMsg error={q.error ?? 'sin datos'} />
  const s = q.data
  return (
    <Seccion titulo="Estado de sincronización" subtitulo={`Disponibilidad de los portales verificada en vivo hace ${s.verificado_hace_s} s.`}>
      <div className="grid gap-3 md:grid-cols-3">
        <Kpi titulo="Último corte procesado" valor={fmtFecha(s.corte?.fecha_corte)} />
        <Kpi
          titulo="Última sincronización automática"
          valor={s.ultima_sincronizacion ? s.ultima_sincronizacion.estado : 'sin ejecuciones'}
          detalle={s.ultima_sincronizacion ? fmtFecha(s.ultima_sincronizacion.inicio) : 'el worker registra cada ejecución'}
        />
        <Kpi titulo="Próxima actualización automática" valor={fmtFecha(s.proxima_sincronizacion)} />
      </div>
      <table className="tabla mt-4 w-full max-w-2xl">
        <thead>
          <tr>
            <th>Fuente del Estado</th>
            <th>Estado</th>
            <th className="text-right">Respuesta</th>
          </tr>
        </thead>
        <tbody>
          {(s.fuentes ?? []).map((f) => (
            <tr key={f.fuente}>
              <td>{f.fuente}</td>
              <td className={f.estado === 'EN_LINEA' ? 'text-bajo' : 'text-alto'}>{f.estado === 'EN_LINEA' ? 'En línea' : f.estado}</td>
              <td className="text-right text-xs">{f.ms} ms</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Seccion>
  )
}

export default function FuentesPage() {
  const q = useQuery({ queryKey: ['fuentes'], queryFn: () => api<Fuentes>('/fuentes') })
  if (q.isLoading) return <Cargando />
  if (q.error) return <ErrorMsg error={q.error} />
  const d = q.data!
  const c = d.cobertura
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-marca-900">Datos y sistema</h1>
        <p className="text-sm text-slate-500">Todos los datos provienen de fuentes oficiales abiertas del Estado peruano. Corte: {fmtFecha(d.corte?.fecha_corte)}.</p>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Kpi titulo="Obras con cuaderno digital" valor={fmtNum(c.obras)} detalle={`${fmtNum(c.obras_historia_completa)} con historia completa`} />
        <Kpi titulo="Enlazadas a CUI" valor={fmtNum(c.obras_con_cui)} detalle="Invierte.pe" />
        <Kpi titulo="Enlazadas a INFOBRAS" valor={fmtNum(c.obras_con_infobras)} detalle={`${fmtNum(c.obras_con_contrato_seace)} con contrato SEACE`} />
        <Kpi titulo="Inversiones con SIAF" valor={fmtNum(c.inversiones_con_siaf)} detalle={`${fmtNum(c.registros_contraloria)} registros de Contraloría`} />
      </div>
      <EstadoSync />
      <Seccion titulo="Limitaciones conocidas">
        <ul className="list-disc space-y-1 pl-5 text-sm">
          {LIMITES.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </Seccion>
      <Seccion titulo="Linaje: archivos oficiales utilizados" subtitulo="URL de origen, tamaño, fecha de modificación declarada por el servidor, fecha de descarga y huella SHA-256.">
        <div className="max-h-[520px] overflow-auto">
          <table className="tabla w-full">
            <thead className="sticky top-0">
              <tr>
                <th>Fuente</th>
                <th>Archivo</th>
                <th className="text-right">Tamaño</th>
                <th>Modificado (servidor)</th>
                <th>Descargado</th>
                <th>SHA-256</th>
              </tr>
            </thead>
            <tbody>
              {d.archivos.map((a) => (
                <tr key={a.ruta}>
                  <td className="text-xs">{a.fuente}</td>
                  <td className="text-xs">
                    <a href={a.url} target="_blank" rel="noopener noreferrer" className="text-marca-600 hover:underline">
                      {a.ruta}
                    </a>
                  </td>
                  <td className="text-right text-xs">{fmtNum(a.bytes / 1e6, 1)} MB</td>
                  <td className="text-xs">{a.last_modified ?? '—'}</td>
                  <td className="text-xs">{fmtFecha(a.descargado_en)}</td>
                  <td className="font-mono text-[10px]">{a.sha256?.slice(0, 16)}…</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Seccion>
    </div>
  )
}
