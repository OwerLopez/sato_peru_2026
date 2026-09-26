import type { ReactNode } from 'react'
import type { Nivel } from '../api'

export function NivelBadge({ nivel, score }: { nivel: Nivel | null | undefined; score?: number | null }) {
  if (!nivel) return <span className="text-xs text-slate-500">sin evaluación</span>
  const cls = { ALTO: 'bg-red-100 text-alto ring-red-200', MEDIO: 'bg-amber-100 text-medio ring-amber-200', BAJO: 'bg-green-100 text-bajo ring-green-200' }[nivel]
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ${cls}`}>
      {nivel}
      {score !== undefined && score !== null && <span className="font-normal opacity-95">{(100 * score).toFixed(0)}%</span>}
    </span>
  )
}

export function Kpi({ titulo, valor, detalle, tono = 'normal' }: { titulo: string; valor: ReactNode; detalle?: ReactNode; tono?: 'normal' | 'alto' | 'medio' }) {
  const c = tono === 'alto' ? 'text-alto' : tono === 'medio' ? 'text-medio' : 'text-marca-800'
  return (
    <div className="tarjeta p-4">
      <div className="etiqueta">{titulo}</div>
      <div className={`mt-1 text-2xl font-bold ${c}`}>{valor}</div>
      {detalle && <div className="mt-1 text-xs text-slate-500">{detalle}</div>}
    </div>
  )
}

export function Cargando({ texto = 'Cargando…' }: { texto?: string }) {
  return <div className="p-6 text-sm text-slate-500">{texto}</div>
}

export function ErrorMsg({ error }: { error: unknown }) {
  return <div className="m-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">No se pudo cargar la información: {String((error as Error)?.message ?? error)}</div>
}

export function Seccion({ titulo, children, accion, subtitulo }: { titulo: string; children: ReactNode; accion?: ReactNode; subtitulo?: ReactNode }) {
  return (
    <section className="tarjeta">
      <header className="flex items-start justify-between gap-3 border-b border-slate-100 px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-700">{titulo}</h2>
          {subtitulo && <p className="mt-0.5 text-xs text-slate-500">{subtitulo}</p>}
        </div>
        {accion}
      </header>
      <div className="p-4">{children}</div>
    </section>
  )
}

export function Paginacion({ pagina, total, tamanio, onChange }: { pagina: number; total: number; tamanio: number; onChange: (p: number) => void }) {
  const paginas = Math.max(1, Math.ceil(total / tamanio))
  return (
    <div className="flex items-center justify-between px-1 pt-3 text-sm text-slate-600">
      <span>
        {total.toLocaleString('es-PE')} resultados · página {pagina} de {paginas}
      </span>
      <div className="flex gap-2">
        <button className="btn" disabled={pagina <= 1} onClick={() => onChange(pagina - 1)}>
          Anterior
        </button>
        <button className="btn" disabled={pagina >= paginas} onClick={() => onChange(pagina + 1)}>
          Siguiente
        </button>
      </div>
    </div>
  )
}

export const SECTORES = ['SANEAMIENTO', 'TRANSPORTE', 'EDUCACION', 'SALUD', 'AGROPECUARIA', 'OTROS', 'SIN_CUI']
export const PROVINCIAS = ['AREQUIPA', 'CAMANA', 'CARAVELI', 'CASTILLA', 'CAYLLOMA', 'CONDESUYOS', 'ISLAY', 'LA UNION']
export const ESTADOS: Record<string, string> = { EN_EJECUCION: 'En ejecución', CULMINADA: 'Culminada', RESUELTA: 'Contrato resuelto', INACTIVA: 'Sin asientos recientes' }
