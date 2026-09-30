import { AlertTriangle, ChevronLeft, ChevronRight, CircleAlert, CircleCheck, Info, RefreshCw, SearchX, TriangleAlert, X } from 'lucide-react'
import { Dialog, Tooltip } from 'radix-ui'
import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { fmtNum, fmtPct, type Nivel } from '../api'
import { GLOSARIO, type Termino } from '../glosario'
import { NIVEL_TEXTO } from '../lib/nivel'

const NIVEL_CLASE: Record<Nivel, string> = {
  ALTO: 'bg-alto-suave text-alto ring-alto/25',
  MEDIO: 'bg-medio-suave text-medio ring-medio/25',
  BAJO: 'bg-bajo-suave text-bajo ring-bajo/25',
}
const NIVEL_PUNTO: Record<Nivel, string> = { ALTO: 'bg-alto', MEDIO: 'bg-medio', BAJO: 'bg-bajo' }
// cada nivel tiene su propia forma de ícono: el nivel se distingue también sin percibir el color
const NIVEL_ICONO = { ALTO: TriangleAlert, MEDIO: CircleAlert, BAJO: CircleCheck } as const

export function NivelBadge({ nivel, score, compacto }: { nivel: Nivel | null | undefined; score?: number | null; compacto?: boolean }) {
  if (!nivel) return <span className="text-xs text-slate-500">Sin evaluación</span>
  const I = NIVEL_ICONO[nivel]
  return (
    <span className={`inline-flex items-center gap-1 rounded-full py-0.5 pr-2 pl-1.5 text-xs font-semibold whitespace-nowrap ring-1 ring-inset ${NIVEL_CLASE[nivel]}`}>
      <I className="size-3.5" aria-hidden />
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
        <span className="num font-display text-3xl font-semibold text-slate-900">{d}</span>
        <span className="text-sm text-slate-600">de 10</span>
        <InfoTip termino="escala" />
      </div>
      <div className="mt-2 flex gap-1" role="img" aria-label={`Posición ${d} de 10`}>
        {Array.from({ length: 10 }, (_, i) => (
          <span key={i} className={`h-2 flex-1 rounded-full ${i < d ? NIVEL_PUNTO[nivel] : 'bg-slate-200'}`} />
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
        {/* área de toque ampliada (after:) sin mover el diseño */}
        <button
          type="button"
          className={`relative inline-flex size-4 shrink-0 items-center justify-center rounded-full text-slate-500 transition-colors after:absolute after:-inset-2.5 hover:text-marca-700 ${className}`}
          aria-label={g ? `Qué significa: ${g.termino}` : 'Más información'}
        >
          <Info className="size-4" />
        </button>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          sideOffset={6}
          collisionPadding={12}
          style={{ zIndex: 'var(--z-ayuda)' }}
          className="max-w-80 animate-aparecer rounded-lg bg-slate-900 px-3.5 py-2.5 text-sm leading-relaxed text-slate-100 shadow-lg"
        >
          {g && <div className="mb-0.5 font-semibold text-white">{g.termino}</div>}
          {texto ?? g?.definicion}
          <Tooltip.Arrow className="fill-slate-900" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  )
}

/** Serie mínima para mostrar la tendencia de una cifra (sin ejes: el texto de la tarjeta dice qué representa). */
export function Tendencia({ valores, tono = 'marca', etiqueta }: { valores: number[]; tono?: 'marca' | 'alto'; etiqueta: string }) {
  if (valores.length < 2) return null
  const w = 120
  const h = 32
  const max = Math.max(...valores)
  const min = Math.min(...valores)
  const y = (v: number) => h - 3 - ((v - min) / (max - min || 1)) * (h - 6)
  const pts = valores.map((v, i) => `${(i / (valores.length - 1)) * w},${y(v)}`).join(' ')
  const color = tono === 'alto' ? 'var(--color-alto)' : 'var(--color-marca-600)'
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-8 w-28 shrink-0 overflow-visible" role="img" aria-label={etiqueta}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
      <circle cx={w} cy={y(valores[valores.length - 1])} r={3} fill={color} />
    </svg>
  )
}

export function Kpi({
  titulo,
  valor,
  unidad,
  detalle,
  tono = 'normal',
  ayuda,
  icono,
  tendencia,
}: {
  titulo: string
  valor: ReactNode
  unidad?: ReactNode
  detalle?: ReactNode
  tono?: 'normal' | 'alto'
  ayuda?: Termino
  icono?: ReactNode
  tendencia?: ReactNode
}) {
  return (
    <div className={`tarjeta relative flex h-full flex-col overflow-hidden p-4 sm:p-5 ${tono === 'alto' ? 'border-t-[3px] border-t-alto' : ''}`}>
      <div className="flex items-start gap-2 text-sm font-semibold text-slate-700">
        {icono && <span className={`mt-0.5 ${tono === 'alto' ? 'text-alto' : 'text-marca-600'}`}>{icono}</span>}
        <span className="min-w-0 flex-1">{titulo}</span>
        {ayuda && <InfoTip termino={ayuda} className="mt-0.5" />}
      </div>
      <div className="mt-2 flex items-end justify-between gap-3">
        <div className="min-w-0">
          <span className={`num font-display text-[1.75rem] leading-none font-semibold tracking-tight whitespace-nowrap sm:text-[2rem] ${tono === 'alto' ? 'text-alto' : 'text-slate-900'}`}>
            {valor}
          </span>
          {unidad && <span className="mt-1 block text-sm font-medium text-slate-600">{unidad}</span>}
        </div>
        {tendencia}
      </div>
      {detalle && <div className="mt-3 border-t border-slate-100 pt-2.5 text-sm leading-snug text-slate-600">{detalle}</div>}
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
        <Esqueleto key={i} className={`h-10 ${i % 3 === 2 ? 'w-2/3' : 'w-full'}`} />
      ))}
    </div>
  )
}

export function CargandoPagina() {
  return (
    <div className="space-y-6" role="status" aria-live="polite">
      <span className="sr-only">Cargando…</span>
      <Esqueleto className="h-9 w-80 max-w-full" />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Esqueleto key={i} className="h-36" />
        ))}
      </div>
      <Esqueleto className="h-96" />
    </div>
  )
}

export function ErrorMsg({ error, reintentar }: { error: unknown; reintentar?: () => void }) {
  const m = error instanceof Error ? error.message : typeof error === 'string' ? error : 'Error desconocido.'
  return (
    <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900" role="alert">
      <AlertTriangle className="mt-0.5 size-5 shrink-0" aria-hidden />
      <div className="flex-1">
        <div className="font-semibold">No se pudo cargar la información</div>
        <div className="mt-0.5 text-red-800">{m}</div>
      </div>
      {reintentar && (
        <button className="btn btn-sm" onClick={reintentar}>
          <RefreshCw className="size-4" aria-hidden />
          Reintentar
        </button>
      )}
    </div>
  )
}

export function Vacio({ titulo, texto, accion }: { titulo: string; texto?: ReactNode; accion?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-4 py-12 text-center">
      <div className="flex size-12 items-center justify-center rounded-full bg-slate-100 text-slate-500">
        <SearchX className="size-6" aria-hidden />
      </div>
      <div className="mt-3 font-display text-base font-semibold text-slate-900">{titulo}</div>
      {texto && <div className="mt-1 max-w-md text-sm text-slate-600">{texto}</div>}
      {accion && <div className="mt-4">{accion}</div>}
    </div>
  )
}

export function Seccion({
  titulo,
  children,
  accion,
  subtitulo,
  ayuda,
  sinRelleno,
  className = '',
  cuerpo = '',
}: {
  titulo: ReactNode
  children: ReactNode
  accion?: ReactNode
  subtitulo?: ReactNode
  ayuda?: Termino
  sinRelleno?: boolean
  className?: string
  cuerpo?: string
}) {
  return (
    <section className={`tarjeta ${className}`}>
      <header className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 border-b border-slate-100 px-4 py-3.5 sm:px-5">
        <div className="min-w-0 flex-1 basis-64">
          <h2 className="flex items-center gap-1.5 text-lg leading-snug font-semibold text-slate-900">
            {titulo}
            {ayuda && <InfoTip termino={ayuda} />}
          </h2>
          {subtitulo && <p className="mt-1 text-sm leading-relaxed text-slate-600">{subtitulo}</p>}
        </div>
        {accion}
      </header>
      <div className={`min-h-0 flex-1 ${sinRelleno ? '' : 'p-4 sm:p-5'} ${cuerpo}`}>{children}</div>
    </section>
  )
}

export function Migas({ items }: { items: { a?: string; l: string }[] }) {
  return (
    <nav aria-label="Ruta de navegación" className="mb-2 text-sm text-slate-600">
      <ol className="flex flex-wrap items-center gap-1">
        {items.map((x, i) => (
          <li key={x.l} className="flex items-center gap-1">
            {i > 0 && <ChevronRight className="size-3.5 text-slate-400" aria-hidden />}
            {x.a ? (
              <Link to={x.a} className="rounded font-semibold text-marca-700 hover:text-marca-900 hover:underline">
                {x.l}
              </Link>
            ) : (
              <span aria-current="page">{x.l}</span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  )
}

export function EncabezadoPagina({ titulo, descripcion, acciones, antes }: { titulo: ReactNode; descripcion?: ReactNode; acciones?: ReactNode; antes?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div className="min-w-0 flex-1 basis-96">
        {antes}
        <h1 className="titulo-pagina">{titulo}</h1>
        {descripcion && <p className="subtitulo-pagina">{descripcion}</p>}
      </div>
      {acciones && <div className="no-imprimir flex flex-wrap items-center gap-2">{acciones}</div>}
    </div>
  )
}

export function Paginacion({ pagina, total, tamanio, onChange }: { pagina: number; total: number; tamanio: number; onChange: (p: number) => void }) {
  const paginas = Math.max(1, Math.ceil(total / tamanio))
  const desde = total === 0 ? 0 : (pagina - 1) * tamanio + 1
  const hasta = Math.min(total, pagina * tamanio)
  const nums = [...new Set([1, pagina - 1, pagina, pagina + 1, paginas])].filter((n) => n >= 1 && n <= paginas).sort((a, b) => a - b)
  return (
    <nav className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 px-4 py-3 text-sm text-slate-600 sm:px-5" aria-label="Paginación">
      <span className="num">
        {fmtNum(desde)}–{fmtNum(hasta)} de {fmtNum(total)}
      </span>
      <div className="flex items-center gap-1">
        <button className="btn-fantasma btn-sm" disabled={pagina <= 1} onClick={() => onChange(pagina - 1)} aria-label="Página anterior">
          <ChevronLeft className="size-4" />
        </button>
        {nums.map((n, i) => (
          <span key={n} className="flex items-center">
            {i > 0 && n - nums[i - 1] > 1 && <span className="px-1 text-slate-500">…</span>}
            <button
              onClick={() => onChange(n)}
              aria-current={n === pagina ? 'page' : undefined}
              aria-label={`Página ${n}`}
              className={`num h-9 min-w-9 rounded-md px-2 text-sm font-semibold transition-colors ${n === pagina ? 'bg-marca-700 text-white' : 'text-slate-700 hover:bg-slate-100'}`}
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
        <Dialog.Overlay style={{ zIndex: 'var(--z-capa)' }} className="fixed inset-0 animate-aparecer bg-slate-900/35" />
        <Dialog.Content style={{ zIndex: 'var(--z-dialogo)' }} className={`fixed inset-y-0 right-0 flex w-full ${ancho} animate-deslizar flex-col bg-white shadow-2xl focus:outline-none`}>
          <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-5 py-4">
            <div className="min-w-0">
              <Dialog.Title className="font-display text-lg font-semibold text-slate-900">{titulo}</Dialog.Title>
              {subtitulo ? <Dialog.Description className="mt-0.5 text-sm text-slate-600">{subtitulo}</Dialog.Description> : <Dialog.Description className="sr-only">Panel de detalle</Dialog.Description>}
            </div>
            <Dialog.Close className="btn-fantasma -mt-1 -mr-2 size-10 p-0" aria-label="Cerrar">
              <X className="size-5" />
            </Dialog.Close>
          </div>
          <div className="flex-1 overflow-y-auto px-5 py-5">{children}</div>
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
    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
      <div className={`h-full rounded-full ${c}`} style={{ width: `${Math.max(0, Math.min(100, (100 * valor) / (max || 1)))}%` }} />
    </div>
  )
}

export function Dato({ l, v, ayuda }: { l: string; v: ReactNode; ayuda?: Termino }) {
  return (
    <div className="min-w-0">
      <dt className="flex items-center gap-1 text-sm text-slate-600">
        {l}
        {ayuda && <InfoTip termino={ayuda} />}
      </dt>
      <dd className="mt-0.5 font-medium break-words text-slate-900">{v ?? '—'}</dd>
    </div>
  )
}

/** Evita que un error de dibujo en una pantalla deje toda la aplicación en blanco. */
export class LimiteDeError extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null }
  static getDerivedStateFromError(error: Error) {
    return { error }
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Error al mostrar la pantalla', error, info.componentStack)
  }
  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="tarjeta p-6" role="alert">
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 size-6 shrink-0 text-alto" aria-hidden />
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Esta pantalla no se pudo mostrar</h2>
            <p className="mt-1 text-sm text-slate-600">Ocurrió un error inesperado en el navegador. Los datos no se modificaron. Recargue la página o vuelva al panorama.</p>
            <div className="mt-4 flex gap-2">
              <button className="btn-primario" onClick={() => window.location.reload()}>
                <RefreshCw className="size-4" aria-hidden />
                Recargar
              </button>
              <a className="btn" href="/">
                Ir al panorama
              </a>
            </div>
          </div>
        </div>
      </div>
    )
  }
}
