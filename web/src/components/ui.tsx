import { AlertTriangle, ChevronLeft, ChevronRight, Info, SearchX, X } from 'lucide-react'
import { Dialog, Tooltip } from 'radix-ui'
import type { ReactNode } from 'react'
import { fmtNum, fmtPct, type Nivel } from '../api'
import { GLOSARIO, type Termino } from '../glosario'
import { NIVEL_TEXTO } from '../lib/nivel'

const NIVEL_CLASE: Record<Nivel, string> = {
  ALTO: 'bg-alto-suave text-alto ring-alto/20',
  MEDIO: 'bg-medio-suave text-medio ring-medio/20',
  BAJO: 'bg-bajo-suave text-bajo ring-bajo/20',
}
const NIVEL_PUNTO: Record<Nivel, string> = { ALTO: 'bg-alto', MEDIO: 'bg-medio', BAJO: 'bg-bajo' }

export function NivelBadge({ nivel, score, compacto }: { nivel: Nivel | null | undefined; score?: number | null; compacto?: boolean }) {
  if (!nivel) return <span className="text-xs text-slate-500">Sin evaluación</span>
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-semibold whitespace-nowrap ring-1 ring-inset ${NIVEL_CLASE[nivel]}`}>
      <span className={`size-1.5 rounded-full ${NIVEL_PUNTO[nivel]}`} aria-hidden />
      {compacto ? NIVEL_TEXTO[nivel] : `Riesgo ${NIVEL_TEXTO[nivel].toLowerCase()}`}
      {score !== undefined && score !== null && <span className="num font-medium opacity-90">· {fmtPct(score)}</span>}
    </span>
  )
}

// Posición relativa de la obra entre todas las evaluadas en el mismo corte (decil del percentil).
export function EscalaRiesgo({ percentil, nivel }: { percentil: number | null | undefined; nivel: Nivel | null | undefined }) {
  if (percentil === null || percentil === undefined || !nivel) return null
  const d = Math.min(10, Math.max(1, Math.ceil(percentil * 10)))
  return (
    <div>
      <div className="flex items-baseline gap-1.5">
        <span className="num text-2xl font-semibold text-slate-900">{d}</span>
        <span className="text-sm text-slate-500">/ 10</span>
        <InfoTip termino="escala" />
      </div>
      <div className="mt-1.5 flex gap-0.5" role="img" aria-label={`Posición ${d} de 10`}>
        {Array.from({ length: 10 }, (_, i) => (
          <span key={i} className={`h-1.5 flex-1 rounded-full ${i < d ? NIVEL_PUNTO[nivel] : 'bg-slate-200'}`} />
        ))}
      </div>
    </div>
  )
}

export function InfoTip({ termino, texto, className = '' }: { termino?: Termino; texto?: ReactNode; className?: string }) {
  const g = termino ? GLOSARIO[termino] : null
  return (
    <Tooltip.Root delayDuration={150}>
      <Tooltip.Trigger asChild>
        <button type="button" className={`inline-flex size-4 shrink-0 items-center justify-center rounded-full text-slate-400 hover:text-marca-600 ${className}`} aria-label={g ? `Qué significa: ${g.termino}` : 'Más información'}>
          <Info className="size-3.5" />
        </button>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content sideOffset={6} collisionPadding={12} className="z-[2000] max-w-72 animate-aparecer rounded-lg bg-slate-900 px-3 py-2 text-xs leading-relaxed text-slate-100 shadow-lg">
          {g && <div className="mb-0.5 font-semibold text-white">{g.termino}</div>}
          {texto ?? g?.definicion}
          <Tooltip.Arrow className="fill-slate-900" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  )
}

export function Kpi({ titulo, valor, detalle, tono = 'normal', ayuda, icono }: { titulo: string; valor: ReactNode; detalle?: ReactNode; tono?: 'normal' | 'alto'; ayuda?: Termino; icono?: ReactNode }) {
  return (
    <div className="tarjeta relative overflow-hidden p-4">
      {tono === 'alto' && <span className="absolute inset-y-0 left-0 w-1 bg-alto" aria-hidden />}
      <div className="flex items-center gap-1.5 text-[13px] font-medium text-slate-600">
        {icono && <span className={tono === 'alto' ? 'text-alto' : 'text-marca-600'}>{icono}</span>}
        {titulo}
        {ayuda && <InfoTip termino={ayuda} />}
      </div>
      <div className={`num mt-1.5 text-2xl font-semibold tracking-tight sm:text-[26px] ${tono === 'alto' ? 'text-alto' : 'text-slate-900'}`}>{valor}</div>
      {detalle && <div className="mt-1 text-xs leading-relaxed text-slate-500">{detalle}</div>}
    </div>
  )
}

export function Esqueleto({ className = '' }: { className?: string }) {
  return <div className={`esqueleto ${className}`} aria-hidden />
}

export function Cargando({ filas = 4, texto = 'Cargando información' }: { filas?: number; texto?: string }) {
  return (
    <div className="space-y-2.5 p-1" role="status" aria-live="polite">
      <span className="sr-only">{texto}…</span>
      {Array.from({ length: filas }, (_, i) => (
        <Esqueleto key={i} className={`h-9 ${i % 3 === 2 ? 'w-2/3' : 'w-full'}`} />
      ))}
    </div>
  )
}

export function CargandoPagina() {
  return (
    <div className="space-y-5" role="status" aria-live="polite">
      <span className="sr-only">Cargando…</span>
      <Esqueleto className="h-8 w-80" />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Esqueleto key={i} className="h-28" />
        ))}
      </div>
      <Esqueleto className="h-80" />
    </div>
  )
}

export function ErrorMsg({ error, reintentar }: { error: unknown; reintentar?: () => void }) {
  const m = error instanceof Error ? error.message : typeof error === 'string' ? error : 'Error desconocido.'
  return (
    <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900" role="alert">
      <AlertTriangle className="mt-0.5 size-4 shrink-0" />
      <div className="flex-1">
        <div className="font-medium">No se pudo cargar la información</div>
        <div className="mt-0.5 text-red-800">{m}</div>
      </div>
      {reintentar && (
        <button className="btn btn-sm" onClick={reintentar}>
          Reintentar
        </button>
      )}
    </div>
  )
}

export function Vacio({ titulo, texto, accion }: { titulo: string; texto?: ReactNode; accion?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-4 py-10 text-center">
      <div className="flex size-10 items-center justify-center rounded-full bg-slate-100 text-slate-500">
        <SearchX className="size-5" />
      </div>
      <div className="mt-3 text-sm font-medium text-slate-800">{titulo}</div>
      {texto && <div className="mt-1 max-w-sm text-sm text-slate-500">{texto}</div>}
      {accion && <div className="mt-3">{accion}</div>}
    </div>
  )
}

export function Seccion({ titulo, children, accion, subtitulo, ayuda, sinRelleno, className = '' }: { titulo: ReactNode; children: ReactNode; accion?: ReactNode; subtitulo?: ReactNode; ayuda?: Termino; sinRelleno?: boolean; className?: string }) {
  return (
    <section className={`tarjeta ${className}`}>
      <header className="flex flex-wrap items-start justify-between gap-x-3 gap-y-2 border-b border-slate-100 px-4 py-3">
        <div className="min-w-0">
          <h2 className="flex items-center gap-1.5 text-[15px] font-semibold text-slate-900">
            {titulo}
            {ayuda && <InfoTip termino={ayuda} />}
          </h2>
          {subtitulo && <p className="mt-0.5 text-[13px] leading-relaxed text-slate-500">{subtitulo}</p>}
        </div>
        {accion}
      </header>
      <div className={`min-h-0 flex-1 ${sinRelleno ? '' : 'p-4'}`}>{children}</div>
    </section>
  )
}

export function EncabezadoPagina({ titulo, descripcion, acciones, antes }: { titulo: ReactNode; descripcion?: ReactNode; acciones?: ReactNode; antes?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        {antes}
        <h1 className="titulo-pagina">{titulo}</h1>
        {descripcion && <p className="subtitulo-pagina">{descripcion}</p>}
      </div>
      {acciones && <div className="flex flex-wrap items-center gap-2">{acciones}</div>}
    </div>
  )
}

export function Paginacion({ pagina, total, tamanio, onChange }: { pagina: number; total: number; tamanio: number; onChange: (p: number) => void }) {
  const paginas = Math.max(1, Math.ceil(total / tamanio))
  const desde = total === 0 ? 0 : (pagina - 1) * tamanio + 1
  const hasta = Math.min(total, pagina * tamanio)
  const nums = [...new Set([1, pagina - 1, pagina, pagina + 1, paginas])].filter((n) => n >= 1 && n <= paginas).sort((a, b) => a - b)
  return (
    <nav className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 px-4 py-3 text-sm text-slate-600" aria-label="Paginación">
      <span className="num">
        {fmtNum(desde)}–{fmtNum(hasta)} de {fmtNum(total)}
      </span>
      <div className="flex items-center gap-1">
        <button className="btn-fantasma btn-sm" disabled={pagina <= 1} onClick={() => onChange(pagina - 1)} aria-label="Página anterior">
          <ChevronLeft className="size-4" />
        </button>
        {nums.map((n, i) => (
          <span key={n} className="flex items-center">
            {i > 0 && n - nums[i - 1] > 1 && <span className="px-1 text-slate-400">…</span>}
            <button
              onClick={() => onChange(n)}
              aria-current={n === pagina ? 'page' : undefined}
              className={`num h-8 min-w-8 rounded-md px-2 text-[13px] font-medium ${n === pagina ? 'bg-marca-700 text-white' : 'text-slate-600 hover:bg-slate-100'}`}
            >
              {fmtNum(n)}
            </button>
          </span>
        ))}
        <button className="btn-fantasma btn-sm" disabled={pagina >= paginas} onClick={() => onChange(pagina + 1)} aria-label="Página siguiente">
          <ChevronRight className="size-4" />
        </button>
      </div>
    </nav>
  )
}

export function Panel({ abierto, onClose, titulo, subtitulo, children, ancho = 'max-w-xl' }: { abierto: boolean; onClose: () => void; titulo: ReactNode; subtitulo?: ReactNode; children: ReactNode; ancho?: string }) {
  return (
    <Dialog.Root open={abierto} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[1500] animate-aparecer bg-slate-900/30 backdrop-blur-[1px]" />
        <Dialog.Content className={`fixed inset-y-0 right-0 z-[1600] flex w-full ${ancho} animate-deslizar flex-col bg-white shadow-2xl focus:outline-none`}>
          <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-5 py-4">
            <div className="min-w-0">
              <Dialog.Title className="text-base font-semibold text-slate-900">{titulo}</Dialog.Title>
              {subtitulo ? <Dialog.Description className="mt-0.5 text-[13px] text-slate-500">{subtitulo}</Dialog.Description> : <Dialog.Description className="sr-only">Panel de detalle</Dialog.Description>}
            </div>
            <Dialog.Close className="btn-fantasma -mr-2 -mt-1 size-9 p-0" aria-label="Cerrar">
              <X className="size-4" />
            </Dialog.Close>
          </div>
          <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

export function Segmentado<T extends string>({ valor, opciones, onChange, etiqueta }: { valor: T; opciones: { v: T; l: ReactNode }[]; onChange: (v: T) => void; etiqueta: string }) {
  return (
    <div className="segmento" role="group" aria-label={etiqueta}>
      {opciones.map((o) => (
        <button key={o.v} type="button" data-activo={o.v === valor} aria-pressed={o.v === valor} onClick={() => onChange(o.v)}>
          {o.l}
        </button>
      ))}
    </div>
  )
}

export function BarraProporcion({ valor, max = 1, tono = 'marca' }: { valor: number; max?: number; tono?: 'marca' | 'alto' | 'medio' | 'bajo' }) {
  const c = { marca: 'bg-marca-500', alto: 'bg-alto', medio: 'bg-medio', bajo: 'bg-bajo' }[tono]
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
      <div className={`h-full rounded-full ${c}`} style={{ width: `${Math.max(0, Math.min(100, (100 * valor) / (max || 1)))}%` }} />
    </div>
  )
}

export function Dato({ l, v, ayuda }: { l: string; v: ReactNode; ayuda?: Termino }) {
  return (
    <div className="min-w-0">
      <dt className="flex items-center gap-1 text-xs text-slate-500">
        {l}
        {ayuda && <InfoTip termino={ayuda} />}
      </dt>
      <dd className="mt-0.5 text-sm break-words text-slate-800">{v ?? '—'}</dd>
    </div>
  )
}
