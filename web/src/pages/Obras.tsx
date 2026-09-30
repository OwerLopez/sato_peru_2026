import { useQuery } from '@tanstack/react-query'
import { PanelRightOpen } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ESTADOS, fmtFecha, fmtNum, nombreObra, qs, SECTOR, titulo, useFiltros, type Nivel, type ObraResumen } from '../api'
import { useAmbito } from '../ambito'
import { VistaPreviaCuaderno } from '../components/Factores'
import { BarraFiltros, ChipsActivos, ResumenNiveles, SelectFiltro } from '../components/Filtros'
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
  const base = { ...params, nivel: '', pagina: 1, tamanio: 1 }
  const contar = (nivel: Nivel | '') => api<{ total: number }>(`/obras${qs({ ...base, nivel })}`).then((x) => x.total)
  const chips = activos
    .filter((k) => k !== 'vista' && k !== 'orden')
    .map((k) => ({
      k,
      l: k === 'q' ? `“${f.q}”` : k === 'nivel' ? `Riesgo ${NIVEL_TEXTO[f.nivel as 'ALTO'].toLowerCase()}` : k === 'sector' ? (SECTOR[f.sector] ?? f.sector) : (ESTADOS[f.estado] ?? f.estado),
      quitar: () => set({ [k]: null }),
    }))
  return (
    <div className="space-y-5">
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
      <ResumenNiveles contar={contar} clave={['obras', base]} valor={f.nivel} onChange={(n) => set({ nivel: n || null })} />
      <section className="tarjeta overflow-hidden">
        <BarraFiltros busqueda={f.q} onBuscar={(q) => set({ q })} placeholder="Nombre de la obra, entidad o CUI">
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
            <ul className={`divide-y divide-slate-100 md:hidden ${r.isFetching ? 'opacity-60' : ''}`} aria-label="Obras">
              {r.data!.items.map((o) => (
                <li key={o.cuaderno_id} className="px-4 py-4">
                  <div className="flex items-start justify-between gap-3">
                    <Link to={`/obras/${o.cuaderno_id}`} className="line-clamp-3 font-semibold text-slate-900 hover:text-marca-800 hover:underline" title={o.denominacion}>
                      {nombreObra(o.denominacion)}
                    </Link>
                    <NivelBadge nivel={o.nivel} score={o.score} compacto />
                  </div>
                  <div className="mt-1 line-clamp-1 text-sm text-slate-600">{o.entidad ?? 'Entidad no identificada'}</div>
                  <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-sm text-slate-700">
                    <span>
                      {titulo(o.provincia)}, {titulo(o.departamento)}
                    </span>
                    <span>{SECTOR[o.sector ?? ''] ?? titulo(o.sector)}</span>
                    {f.vista === 'vigentes' ? <span>Último asiento: {fmtFecha(o.ultimo_asiento)}</span> : <span>{ESTADOS[o.estado_observado] ?? o.estado_observado}</span>}
                  </div>
                  {o.prediccion_id && (
                    <button className="btn btn-sm mt-3" onClick={() => setSel(o)}>
                      <PanelRightOpen className="size-4" aria-hidden />
                      Vista previa del riesgo
                    </button>
                  )}
                </li>
              ))}
            </ul>
            <div className={`hidden overflow-x-auto transition-opacity md:block ${r.isFetching ? 'opacity-60' : ''}`}>
              <table className="tabla min-w-[980px]">
                <thead>
                  <tr>
                    <th>Obra</th>
                    <th>
                      <span className="inline-flex items-center gap-1">
                        Riesgo estimado <InfoTip termino="probabilidad" />
                      </span>
                    </th>
                    <th>Ubicación</th>
                    <th>Sector</th>
                    <th>{f.vista === 'vigentes' ? 'Último asiento' : 'Estado'}</th>
                    <th>
                      <span className="sr-only">Acciones</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {r.data!.items.map((o) => (
                    <tr key={o.cuaderno_id}>
                      <td className="max-w-md">
                        <Link to={`/obras/${o.cuaderno_id}`} className="line-clamp-2 font-semibold text-slate-900 hover:text-marca-800 hover:underline" title={o.denominacion}>
                          {nombreObra(o.denominacion)}
                        </Link>
                        <div className="mt-0.5 truncate text-sm text-slate-600">
                          {o.entidad ?? 'Entidad no identificada'}
                          {o.cui ? ` · CUI ${o.cui}` : ''}
                        </div>
                      </td>
                      <td className="whitespace-nowrap">
                        <NivelBadge nivel={o.nivel} score={o.score} compacto />
                        <div className="mt-1 text-xs text-slate-600">
                          {o.fecha_corte ? `${o.tipo_prediccion === 'vigente' ? 'Vigente' : 'Histórica'} · ${fmtFecha(o.fecha_corte)}` : ''}
                        </div>
                      </td>
                      <td className="whitespace-nowrap">
                        {titulo(o.provincia)}
                        <div className="text-sm text-slate-600">{titulo(o.departamento)}</div>
                      </td>
                      <td>{SECTOR[o.sector ?? ''] ?? titulo(o.sector)}</td>
                      <td className="whitespace-nowrap">
                        {f.vista === 'vigentes' ? (
                          fmtFecha(o.ultimo_asiento)
                        ) : (
                          <>
                            {ESTADOS[o.estado_observado] ?? o.estado_observado}
                            {o.fecha_atraso && <div className="text-sm font-semibold text-alto">Atraso formal: {fmtFecha(o.fecha_atraso)}</div>}
                          </>
                        )}
                      </td>
                      <td className="text-right">
                        {o.prediccion_id && (
                          <button className="btn btn-sm whitespace-nowrap" onClick={() => setSel(o)} aria-label={`Vista previa de ${nombreObra(o.denominacion).slice(0, 60)}`}>
                            <PanelRightOpen className="size-4" aria-hidden />
                            Vista previa
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
      <p className="text-sm text-slate-600">{r.data ? `${fmtNum(r.data.total)} obras encontradas.` : ''} La probabilidad se recalcula cada mes con la información registrada hasta el corte.</p>
      <Panel abierto={!!sel} onClose={() => setSel(null)} titulo="Vista previa de la alerta" subtitulo="Predicción más reciente de la obra y sus principales factores">
        {sel?.prediccion_id && <VistaPreviaCuaderno prediccionId={sel.prediccion_id} cuadernoId={sel.cuaderno_id} nombre={nombreObra(sel.denominacion)} />}
      </Panel>
    </div>
  )
}
