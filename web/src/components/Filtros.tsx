import { useQueries } from '@tanstack/react-query'
import { CircleAlert, CircleCheck, Layers, Search, TriangleAlert, X } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { fmtNum, fmtPct, type Nivel } from '../api'

export function BarraFiltros({ children, busqueda, onBuscar, placeholder }: { children?: ReactNode; busqueda: string; onBuscar: (q: string) => void; placeholder: string }) {
  return (
    <div className="flex flex-wrap items-end gap-3 border-b border-slate-100 p-4 sm:px-5">
      <Busqueda key={busqueda} inicial={busqueda} onBuscar={onBuscar} placeholder={placeholder} />
      {children}
    </div>
  )
}

function Busqueda({ inicial, onBuscar, placeholder }: { inicial: string; onBuscar: (q: string) => void; placeholder: string }) {
  const [q, setQ] = useState(inicial)
  return (
    <form
      role="search"
      className="relative min-w-0 flex-1 basis-64"
      onSubmit={(e) => {
        e.preventDefault()
        onBuscar(q.trim())
      }}
    >
      <label className="flex flex-col gap-1">
        <span className="text-xs font-semibold text-slate-700">Buscar en la lista</span>
        <span className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-500" aria-hidden />
          <input className="entrada w-full pr-10 pl-9" type="search" value={q} maxLength={120} onChange={(e) => setQ(e.target.value)} placeholder={placeholder} />
          {q && (
            <button
              type="button"
              className="absolute top-1/2 right-1.5 flex size-8 -translate-y-1/2 items-center justify-center rounded text-slate-500 hover:bg-slate-100 hover:text-slate-800"
              aria-label="Borrar búsqueda"
              onClick={() => {
                setQ('')
                onBuscar('')
              }}
            >
              <X className="size-4" />
            </button>
          )}
        </span>
      </label>
    </form>
  )
}

export function SelectFiltro({ etiqueta, valor, onChange, opciones, todos = 'Todos' }: { etiqueta: string; valor: string; onChange: (v: string) => void; opciones: { v: string; l: string }[]; todos?: string | null }) {
  return (
    <label className="flex min-w-0 flex-col gap-1">
      <span className="text-xs font-semibold text-slate-700">{etiqueta}</span>
      <select className="entrada w-44 max-w-full" value={valor} onChange={(e) => onChange(e.target.value)}>
        {todos !== null && <option value="">{todos}</option>}
        {opciones.map((o) => (
          <option key={o.v} value={o.v}>
            {o.l}
          </option>
        ))}
      </select>
    </label>
  )
}

export function ChipsActivos({ chips, onLimpiar }: { chips: { k: string; l: string; quitar: () => void }[]; onLimpiar: () => void }) {
  if (!chips.length) return null
  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 px-4 py-2.5 sm:px-5">
      <span className="text-sm text-slate-600">Filtros aplicados:</span>
      {chips.map((c) => (
        <button
          key={c.k}
          onClick={c.quitar}
          className="inline-flex items-center gap-1.5 rounded-full bg-marca-50 px-3 py-1 text-sm font-semibold text-marca-800 ring-1 ring-marca-200 transition-colors hover:bg-marca-100"
          aria-label={`Quitar filtro: ${c.l}`}
        >
          {c.l}
          <X className="size-3.5" aria-hidden />
        </button>
      ))}
      <button className="enlace ml-1 text-sm" onClick={onLimpiar}>
        Limpiar todo
      </button>
    </div>
  )
}

const NIVELES: { n: Nivel; l: string; icono: typeof TriangleAlert; color: string; barra: string }[] = [
  { n: 'ALTO', l: 'Riesgo alto', icono: TriangleAlert, color: 'text-alto', barra: 'bg-alto' },
  { n: 'MEDIO', l: 'Riesgo medio', icono: CircleAlert, color: 'text-medio', barra: 'bg-medio' },
  { n: 'BAJO', l: 'Riesgo bajo', icono: CircleCheck, color: 'text-bajo', barra: 'bg-bajo' },
]

/** Resumen por nivel de riesgo que también filtra la lista (conteos reales con los demás filtros aplicados). */
export function ResumenNiveles({ contar, clave, valor, onChange }: { contar: (nivel: Nivel | '') => Promise<number>; clave: unknown; valor: string; onChange: (n: string) => void }) {
  const qs = useQueries({
    queries: (['', 'ALTO', 'MEDIO', 'BAJO'] as const).map((n) => ({ queryKey: ['conteo-nivel', clave, n], queryFn: () => contar(n), staleTime: 60_000 })),
  })
  const [total, ...por] = qs.map((q) => q.data)
  const bloque = (activo: boolean) =>
    `group relative flex min-w-0 flex-col items-start rounded-xl border p-3.5 text-left transition-colors duration-150 sm:p-4 ${
      activo ? 'border-marca-600 bg-marca-50 ring-2 ring-marca-600/25' : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'
    }`
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4" role="group" aria-label="Resumen por nivel de riesgo (filtra la lista)">
      <button type="button" aria-pressed={valor === ''} className={bloque(valor === '')} onClick={() => onChange('')}>
        <span className="flex items-center gap-1.5 text-sm font-semibold text-slate-700">
          <Layers className="size-4 text-marca-600" aria-hidden /> Todas las evaluadas
        </span>
        <span className="num mt-1 font-display text-2xl font-semibold text-slate-900">{total === undefined ? '…' : fmtNum(total)}</span>
        <span className="text-sm text-slate-600">obras</span>
      </button>
      {NIVELES.map((x, i) => {
        const v = por[i]
        const prop = total && v !== undefined ? v / total : null
        return (
          <button key={x.n} type="button" aria-pressed={valor === x.n} className={bloque(valor === x.n)} onClick={() => onChange(valor === x.n ? '' : x.n)}>
            <span className={`flex items-center gap-1.5 text-sm font-semibold ${x.color}`}>
              <x.icono className="size-4" aria-hidden /> {x.l}
            </span>
            <span className="num mt-1 font-display text-2xl font-semibold text-slate-900">{v === undefined ? '…' : fmtNum(v)}</span>
            <span className="text-sm text-slate-600">{prop === null ? 'obras' : `${fmtPct(prop, 1)} del total`}</span>
            <span className="mt-2 block h-1.5 w-full overflow-hidden rounded-full bg-slate-100" aria-hidden>
              <span className={`block h-full rounded-full ${x.barra}`} style={{ width: `${100 * (prop ?? 0)}%` }} />
            </span>
          </button>
        )
      })}
    </div>
  )
}
