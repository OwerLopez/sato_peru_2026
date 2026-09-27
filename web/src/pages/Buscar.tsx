import { useQuery } from '@tanstack/react-query'
import { ArrowRight } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, ESTADO_OP, ESTADOS, fmtNum, qs, titulo, type Nivel, type ObraResumen } from '../api'
import { useAmbito } from '../ambito'
import { Cargando, EncabezadoPagina, ErrorMsg, NivelBadge, Seccion, Vacio } from '../components/ui'

interface ItemK {
  codigo_infobras: string
  nombre: string
  departamento: string
  provincia: string
  entidad: string
  estado_operativo: string
  score: number | null
  nivel: Nivel | null
}

export default function Buscar() {
  const [sp] = useSearchParams()
  const q = (sp.get('q') ?? '').trim()
  const { departamento } = useAmbito()
  const p = { q, departamento, tamanio: 8 }
  const o = useQuery({ queryKey: ['buscar-o', p], queryFn: () => api<{ total: number; items: ObraResumen[] }>(`/obras${qs(p)}`), enabled: !!q })
  const c = useQuery({ queryKey: ['buscar-c', p], queryFn: () => api<{ total: number; items: ItemK[] }>(`/cartera${qs(p)}`), enabled: !!q })
  if (!q) return <Vacio titulo="Escriba un término de búsqueda" texto="Puede buscar por nombre de la obra, entidad, CUI o código INFOBRAS." />
  return (
    <div className="space-y-5">
      <EncabezadoPagina titulo={`Resultados para “${q}”`} descripcion={departamento ? `En ${titulo(departamento)}. Cambie el ámbito para buscar en todo el Perú.` : 'En todo el Perú.'} />
      <div className="grid gap-5 lg:grid-cols-2">
        <Seccion titulo="Obras con cuaderno de obra digital" subtitulo={o.data ? `${fmtNum(o.data.total)} coincidencias` : undefined} sinRelleno>
          {o.isLoading ? (
            <div className="p-4">
              <Cargando />
            </div>
          ) : o.error ? (
            <div className="p-4">
              <ErrorMsg error={o.error} />
            </div>
          ) : o.data!.items.length === 0 ? (
            <Vacio titulo="Sin coincidencias" />
          ) : (
            <ul className="divide-y divide-slate-100">
              {o.data!.items.map((x) => (
                <li key={x.cuaderno_id}>
                  <Link to={`/obras/${x.cuaderno_id}`} className="flex items-start gap-3 px-4 py-3 hover:bg-slate-50">
                    <span className="min-w-0 flex-1">
                      <span className="line-clamp-2 text-sm font-medium text-slate-900">{x.denominacion}</span>
                      <span className="mt-0.5 block truncate text-xs text-slate-500">
                        {titulo(x.provincia)}, {titulo(x.departamento)} · {ESTADOS[x.estado_observado] ?? x.estado_observado}
                      </span>
                    </span>
                    <NivelBadge nivel={x.nivel} compacto />
                  </Link>
                </li>
              ))}
            </ul>
          )}
          {o.data && o.data.total > 8 && (
            <div className="border-t border-slate-100 px-4 py-3">
              <Link to={`/obras?vista=todas&q=${encodeURIComponent(q)}`} className="enlace inline-flex items-center gap-1 text-sm">
                Ver las {fmtNum(o.data.total)} obras <ArrowRight className="size-4" />
              </Link>
            </div>
          )}
        </Seccion>
        <Seccion titulo="Cartera nacional INFOBRAS" subtitulo={c.data ? `${fmtNum(c.data.total)} coincidencias` : undefined} sinRelleno>
          {c.isLoading ? (
            <div className="p-4">
              <Cargando />
            </div>
          ) : c.error ? (
            <div className="p-4">
              <ErrorMsg error={c.error} />
            </div>
          ) : c.data!.items.length === 0 ? (
            <Vacio titulo="Sin coincidencias" />
          ) : (
            <ul className="divide-y divide-slate-100">
              {c.data!.items.map((x) => (
                <li key={x.codigo_infobras}>
                  <Link to={`/cartera/${x.codigo_infobras}`} className="flex items-start gap-3 px-4 py-3 hover:bg-slate-50">
                    <span className="min-w-0 flex-1">
                      <span className="line-clamp-2 text-sm font-medium text-slate-900">{x.nombre}</span>
                      <span className="mt-0.5 block truncate text-xs text-slate-500">
                        {titulo(x.provincia)}, {titulo(x.departamento)} · {ESTADO_OP[x.estado_operativo] ?? x.estado_operativo}
                      </span>
                    </span>
                    <NivelBadge nivel={x.nivel} compacto />
                  </Link>
                </li>
              ))}
            </ul>
          )}
          {c.data && c.data.total > 8 && (
            <div className="border-t border-slate-100 px-4 py-3">
              <Link to={`/cartera?estado=&q=${encodeURIComponent(q)}`} className="enlace inline-flex items-center gap-1 text-sm">
                Ver las {fmtNum(c.data.total)} obras <ArrowRight className="size-4" />
              </Link>
            </div>
          )}
        </Seccion>
      </div>
    </div>
  )
}
