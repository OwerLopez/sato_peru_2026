import { Search, X } from 'lucide-react'
import { useState, type ReactNode } from 'react'

export function BarraFiltros({ children, busqueda, onBuscar, placeholder }: { children?: ReactNode; busqueda: string; onBuscar: (q: string) => void; placeholder: string }) {
  return (
    <div className="flex flex-wrap items-end gap-2 border-b border-slate-100 p-3">
      <Busqueda key={busqueda} inicial={busqueda} onBuscar={onBuscar} placeholder={placeholder} />
      {children}
    </div>
  )
}

function Busqueda({ inicial, onBuscar, placeholder }: { inicial: string; onBuscar: (q: string) => void; placeholder: string }) {
  const [q, setQ] = useState(inicial)
  return (
      <form
        className="relative min-w-56 flex-1"
        onSubmit={(e) => {
          e.preventDefault()
          onBuscar(q.trim())
        }}
      >
        <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" />
        <input className="entrada w-full pr-9 pl-9" value={q} maxLength={120} onChange={(e) => setQ(e.target.value)} placeholder={placeholder} aria-label="Buscar" />
        {q && (
          <button
            type="button"
            className="absolute top-1/2 right-2 -translate-y-1/2 rounded p-1 text-slate-400 hover:text-slate-700"
            aria-label="Borrar búsqueda"
            onClick={() => {
              setQ('')
              onBuscar('')
            }}
          >
            <X className="size-3.5" />
          </button>
        )}
      </form>
  )
}

export function SelectFiltro({ etiqueta, valor, onChange, opciones, todos = 'Todos' }: { etiqueta: string; valor: string; onChange: (v: string) => void; opciones: { v: string; l: string }[]; todos?: string | null }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs font-medium text-slate-500">{etiqueta}</span>
      <select className="entrada w-40 sm:w-44" value={valor} onChange={(e) => onChange(e.target.value)}>
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
    <div className="flex flex-wrap items-center gap-1.5 border-b border-slate-100 px-3 py-2">
      <span className="text-xs text-slate-500">Filtros:</span>
      {chips.map((c) => (
        <button key={c.k} onClick={c.quitar} className="inline-flex items-center gap-1 rounded-full bg-marca-50 px-2.5 py-0.5 text-xs font-medium text-marca-800 ring-1 ring-marca-100 hover:bg-marca-100">
          {c.l}
          <X className="size-3" aria-label="quitar" />
        </button>
      ))}
      <button className="enlace ml-1 text-xs" onClick={onLimpiar}>
        Limpiar todo
      </button>
    </div>
  )
}
