import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api, ESTADO_OP, fmtFecha, fmtMillones, fmtNum, fmtPct, qs, titulo, useFiltros, type Nivel } from '../api'
import { useAmbito } from '../ambito'
import { BarraFiltros, ChipsActivos, SelectFiltro } from '../components/Filtros'
import { Cargando, EncabezadoPagina, ErrorMsg, InfoTip, NivelBadge, Paginacion, Vacio } from '../components/ui'
import { NIVEL_TEXTO } from '../lib/nivel'
import { useFiltrosUrl } from '../lib/filtrosUrl'

interface Item {
  codigo_infobras: string
  nombre: string
  departamento: string
  provincia: string
  tipo_obra: string
  modalidad: string
  costo: number | null
  estado_operativo: string
  fecha_inicio: string
  fin_programado: string
  fin_real: string | null
  sobreplazo: number | null
  retraso_significativo: number | null
  entidad: string
  modelo: string | null
  score: number | null
  nivel: Nivel | null
}

const TAM = 25
const DEF = { estado: 'ACTIVA', q: '', tipo_obra: '', modalidad: '', nivel: '', orden: 'riesgo' }
const ORDEN: Record<string, string> = { riesgo: 'Mayor riesgo', monto: 'Mayor monto', reciente: 'Inicio más reciente' }

function Resultado({ o }: { o: Item }) {
  if (o.retraso_significativo === null) return <span className="text-slate-500">Aún no determinable</span>
  if (o.retraso_significativo)
    return <span className="font-medium text-alto">Con retraso significativo{o.sobreplazo !== null ? ` (+${fmtPct(o.sobreplazo)} del plazo)` : ''}</span>
  return <span className="text-bajo">Sin retraso significativo</span>
}

export default function Cartera() {
  const { departamento } = useAmbito()
  const { valores: f, pagina, set, limpiar, activos } = useFiltrosUrl(DEF)
  const filtros = useFiltros()
  const params = { ...f, departamento, pagina, tamanio: TAM }
  const r = useQuery({ queryKey: ['cartera', params], queryFn: () => api<{ total: number; items: Item[] }>(`/cartera${qs(params)}`), placeholderData: (p) => p })
  const activa = f.estado === 'ACTIVA'
  const chips = activos
    .filter((k) => k !== 'orden' && k !== 'estado')
    .map((k) => ({ k, l: k === 'q' ? `“${f.q}”` : k === 'nivel' ? `Riesgo ${NIVEL_TEXTO[f.nivel as 'ALTO'].toLowerCase()}` : f[k as keyof typeof f], quitar: () => set({ [k]: null }) }))
  return (
    <div className="space-y-4">
      <EncabezadoPagina
        titulo="Cartera nacional de obras"
        descripcion={
          <>
            Obras públicas registradas en INFOBRAS <InfoTip termino="cartera" className="align-[-2px]" /> de todas las modalidades y sectores. Para cada obra en ejecución se estima la
            probabilidad de terminar con retraso significativo <InfoTip termino="retraso_significativo" className="align-[-2px]" />, al inicio y luego cada mes con la ejecución del gasto
            (SIAF).
          </>
        }
      />
      <section className="tarjeta overflow-hidden">
        <BarraFiltros busqueda={f.q} onBuscar={(q) => set({ q })} placeholder="Buscar por obra, entidad, CUI o código INFOBRAS">
          <SelectFiltro etiqueta="Situación" valor={f.estado} onChange={(v) => set({ estado: v })} todos="Todas" opciones={Object.entries(ESTADO_OP).filter(([k]) => k !== 'OTRO').map(([v, l]) => ({ v, l }))} />
          <SelectFiltro etiqueta="Nivel de riesgo" valor={f.nivel} onChange={(v) => set({ nivel: v })} opciones={(['ALTO', 'MEDIO', 'BAJO'] as const).map((n) => ({ v: n, l: NIVEL_TEXTO[n] }))} />
          <SelectFiltro etiqueta="Tipo de obra" valor={f.tipo_obra} onChange={(v) => set({ tipo_obra: v })} opciones={(filtros.data?.tipos_obra ?? []).map((t) => ({ v: t, l: t }))} />
          <SelectFiltro etiqueta="Modalidad" valor={f.modalidad} onChange={(v) => set({ modalidad: v })} todos="Todas" opciones={(filtros.data?.modalidades ?? []).map((t) => ({ v: t, l: t }))} />
          <SelectFiltro etiqueta="Ordenar por" valor={f.orden} onChange={(v) => set({ orden: v })} todos={null} opciones={Object.entries(ORDEN).map(([v, l]) => ({ v, l }))} />
        </BarraFiltros>
        <ChipsActivos chips={chips} onLimpiar={limpiar} />
        {r.isLoading ? (
          <div className="p-4">
            <Cargando filas={8} />
          </div>
        ) : r.error ? (
          <div className="p-4">
            <ErrorMsg error={r.error} reintentar={() => r.refetch()} />
          </div>
        ) : r.data!.items.length === 0 ? (
          <Vacio titulo="No hay obras con estos filtros" texto="Pruebe con otra búsqueda o amplíe el ámbito geográfico." accion={<button className="btn" onClick={limpiar}>Quitar filtros</button>} />
        ) : (
          <>
            <div className={`overflow-x-auto transition-opacity ${r.isFetching ? 'opacity-60' : ''}`}>
              <table className="tabla min-w-[920px]">
                <thead>
                  <tr>
                    <th>Obra</th>
                    <th>Ubicación</th>
                    <th>
                      <span className="inline-flex items-center gap-1">
                        Riesgo estimado <InfoTip termino="probabilidad" />
                      </span>
                    </th>
                    <th>Tipo y modalidad</th>
                    <th className="text-right">Costo</th>
                    <th>Plazo</th>
                    {!activa && <th>Resultado observado</th>}
                  </tr>
                </thead>
                <tbody>
                  {r.data!.items.map((o) => (
                    <tr key={o.codigo_infobras}>
                      <td className="max-w-md">
                        <Link to={`/cartera/${o.codigo_infobras}`} className="line-clamp-2 font-medium text-slate-900 hover:text-marca-700 hover:underline">
                          {o.nombre}
                        </Link>
                        <div className="mt-0.5 truncate text-xs text-slate-500">
                          {o.entidad} · {ESTADO_OP[o.estado_operativo] ?? o.estado_operativo}
                        </div>
                      </td>
                      <td className="text-[13px] whitespace-nowrap">
                        {titulo(o.provincia)}
                        <div className="text-xs text-slate-500">{titulo(o.departamento)}</div>
                      </td>
                      <td className="whitespace-nowrap">
                        <NivelBadge nivel={o.nivel} score={o.score} compacto />
                        <div className="mt-0.5 text-xs text-slate-500">{o.modelo === 'seguimiento' ? 'Con seguimiento del gasto' : o.modelo ? 'Estimado al inicio' : ''}</div>
                      </td>
                      <td className="text-[13px]">
                        {o.tipo_obra}
                        <div className="text-xs text-slate-500">{o.modalidad}</div>
                      </td>
                      <td className="num text-right text-[13px] whitespace-nowrap">{fmtMillones(o.costo)}</td>
                      <td className="text-[13px] whitespace-nowrap">
                        Inicio {fmtFecha(o.fecha_inicio)}
                        <div className="text-xs text-slate-500">Fin programado {fmtFecha(o.fin_programado)}</div>
                      </td>
                      {!activa && (
                        <td className="text-[13px]">
                          <Resultado o={o} />
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Paginacion pagina={pagina} total={r.data!.total} tamanio={TAM} onChange={(p) => set({ pagina: p })} />
          </>
        )}
      </section>
      <p className="text-xs text-slate-500">{r.data ? `${fmtNum(r.data.total)} obras encontradas.` : ''} Las obras en ejecución sin registros en los últimos 12 meses no se evalúan porque su situación real es desconocida.</p>
    </div>
  )
}
