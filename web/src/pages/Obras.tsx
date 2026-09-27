import { useQuery } from '@tanstack/react-query'
import { Eye } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ESTADOS, fmtFecha, fmtNum, qs, SECTOR, titulo, useFiltros, type ObraResumen } from '../api'
import { useAmbito } from '../ambito'
import { VistaPreviaCuaderno } from '../components/Factores'
import { BarraFiltros, ChipsActivos, SelectFiltro } from '../components/Filtros'
import { Cargando, EncabezadoPagina, ErrorMsg, InfoTip, NivelBadge, Paginacion, Panel, Segmentado, Vacio } from '../components/ui'
import { NIVEL_TEXTO } from '../lib/nivel'
import { useFiltrosUrl } from '../lib/filtrosUrl'

const TAM = 25
const DEF = { vista: 'vigentes', q: '', sector: '', estado: '', nivel: '', orden: 'riesgo' }
const ORDEN: Record<string, string> = { riesgo: 'Mayor riesgo', reciente: 'Actividad reciente', nombre: 'Nombre' }

export default function Obras() {
  const { departamento } = useAmbito()
  const { valores: f, pagina, set, limpiar, activos } = useFiltrosUrl(DEF)
  const filtros = useFiltros()
  const [sel, setSel] = useState<ObraResumen | null>(null)
  const params = { q: f.q, sector: f.sector, estado: f.vista === 'vigentes' ? '' : f.estado, nivel: f.nivel, orden: f.orden, solo_vigentes: f.vista === 'vigentes', departamento, pagina, tamanio: TAM }
  const r = useQuery({ queryKey: ['obras', params], queryFn: () => api<{ total: number; items: ObraResumen[] }>(`/obras${qs(params)}`), placeholderData: (p) => p })
  const chips = activos
    .filter((k) => k !== 'vista' && k !== 'orden')
    .map((k) => ({
      k,
      l: k === 'q' ? `“${f.q}”` : k === 'nivel' ? `Riesgo ${NIVEL_TEXTO[f.nivel as 'ALTO'].toLowerCase()}` : k === 'sector' ? (SECTOR[f.sector] ?? f.sector) : (ESTADOS[f.estado] ?? f.estado),
      quitar: () => set({ [k]: null }),
    }))
  return (
    <div className="space-y-4">
      <EncabezadoPagina
        titulo="Alertas del cuaderno de obra digital"
        descripcion={
          <>
            Contratos de obra con cuaderno de obra digital (OECE), integrados con Invierte.pe, SIAF, INFOBRAS y SEACE. Para cada obra en ejecución se estima la probabilidad de
            registrar un atraso formal <InfoTip termino="atraso_formal" className="align-[-2px]" /> en los próximos 60 días.
          </>
        }
        acciones={
          <Segmentado
            etiqueta="Obras mostradas"
            valor={f.vista}
            onChange={(v) => set({ vista: v, estado: null })}
            opciones={[
              { v: 'vigentes', l: 'En ejecución' },
              { v: 'todas', l: 'Todas (incluye históricas)' },
            ]}
          />
        }
      />
      <section className="tarjeta overflow-hidden">
        <BarraFiltros busqueda={f.q} onBuscar={(q) => set({ q })} placeholder="Buscar por nombre de la obra, entidad o CUI">
          <SelectFiltro
            etiqueta="Nivel de riesgo"
            valor={f.nivel}
            onChange={(v) => set({ nivel: v })}
            opciones={(['ALTO', 'MEDIO', 'BAJO'] as const).map((n) => ({ v: n, l: NIVEL_TEXTO[n] }))}
          />
          <SelectFiltro etiqueta="Sector" valor={f.sector} onChange={(v) => set({ sector: v })} opciones={(filtros.data?.sectores ?? []).map((s) => ({ v: s, l: SECTOR[s] ?? titulo(s) }))} />
          {f.vista === 'todas' && (
            <SelectFiltro etiqueta="Estado" valor={f.estado} onChange={(v) => set({ estado: v })} opciones={Object.entries(ESTADOS).map(([v, l]) => ({ v, l }))} />
          )}
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
          <Vacio titulo="No hay obras con estos filtros" texto="Pruebe con otra búsqueda, otro nivel de riesgo o amplíe el ámbito geográfico." accion={<button className="btn" onClick={limpiar}>Quitar filtros</button>} />
        ) : (
          <>
            <div className={`overflow-x-auto transition-opacity ${r.isFetching ? 'opacity-60' : ''}`}>
              <table className="tabla min-w-[860px]">
                <thead>
                  <tr>
                    <th>Obra</th>
                    <th>Ubicación</th>
                    <th>Sector</th>
                    <th>
                      <span className="inline-flex items-center gap-1">
                        Riesgo estimado <InfoTip termino="probabilidad" />
                      </span>
                    </th>
                    <th>{f.vista === 'vigentes' ? 'Último asiento' : 'Estado'}</th>
                    <th className="w-10">
                      <span className="sr-only">Acciones</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {r.data!.items.map((o) => (
                    <tr key={o.cuaderno_id}>
                      <td className="max-w-md">
                        <Link to={`/obras/${o.cuaderno_id}`} className="line-clamp-2 font-medium text-slate-900 hover:text-marca-700 hover:underline">
                          {o.denominacion}
                        </Link>
                        <div className="mt-0.5 truncate text-xs text-slate-500">
                          {o.entidad ?? 'Entidad no identificada'}
                          {o.cui ? ` · CUI ${o.cui}` : ''}
                        </div>
                      </td>
                      <td className="text-[13px] whitespace-nowrap">
                        {titulo(o.provincia)}
                        <div className="text-xs text-slate-500">{titulo(o.departamento)}</div>
                      </td>
                      <td className="text-[13px]">{SECTOR[o.sector ?? ''] ?? titulo(o.sector)}</td>
                      <td className="whitespace-nowrap">
                        <NivelBadge nivel={o.nivel} score={o.score} compacto />
                        <div className="mt-0.5 text-xs text-slate-500">
                          {o.fecha_corte ? `${o.tipo_prediccion === 'vigente' ? 'Vigente' : 'Histórica'} · ${fmtFecha(o.fecha_corte)}` : ''}
                        </div>
                      </td>
                      <td className="text-[13px] whitespace-nowrap">
                        {f.vista === 'vigentes' ? (
                          fmtFecha(o.ultimo_asiento)
                        ) : (
                          <>
                            {ESTADOS[o.estado_observado] ?? o.estado_observado}
                            {o.fecha_atraso && <div className="text-xs font-medium text-alto">Atraso formal: {fmtFecha(o.fecha_atraso)}</div>}
                          </>
                        )}
                      </td>
                      <td>
                        {o.prediccion_id && (
                          <button className="btn-fantasma btn-sm" onClick={() => setSel(o)} aria-label={`Vista previa de ${o.denominacion.slice(0, 60)}`} title="Vista previa">
                            <Eye className="size-4" />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Paginacion pagina={pagina} total={r.data!.total} tamanio={TAM} onChange={(p) => set({ pagina: p })} />
          </>
        )}
      </section>
      <p className="text-xs text-slate-500">{r.data ? `${fmtNum(r.data.total)} obras encontradas.` : ''} La probabilidad se recalcula cada mes con la información registrada hasta el corte.</p>
      <Panel abierto={!!sel} onClose={() => setSel(null)} titulo="Vista previa de la alerta" subtitulo="Predicción más reciente de la obra y sus principales factores">
        {sel?.prediccion_id && <VistaPreviaCuaderno prediccionId={sel.prediccion_id} cuadernoId={sel.cuaderno_id} nombre={sel.denominacion} />}
      </Panel>
    </div>
  )
}
