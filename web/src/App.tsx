import { useQuery } from '@tanstack/react-query'
import { Activity, BarChart3, BookOpen, Building2, Database, ExternalLink, FileText, LayoutDashboard, LogIn, LogOut, Mail, MapPin, Menu, Search, ShieldCheck, X } from 'lucide-react'
import { Dialog } from 'radix-ui'
import { lazy, Suspense, useEffect, useState, type ReactNode } from 'react'
import { Navigate, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { api, fmtFecha, qs, titulo, useEstado } from './api'
import { useAmbito } from './ambito'
import { useAuth } from './auth'
import { CargandoPagina, LimiteDeError, Vacio } from './components/ui'

// Cada página se descarga al visitarla: el mapa y los gráficos no se cargan en pantallas que no los usan
const Buscar = lazy(() => import('./pages/Buscar'))
const Cartera = lazy(() => import('./pages/Cartera'))
const CarteraDetalle = lazy(() => import('./pages/CarteraDetalle'))
const Comparador = lazy(() => import('./pages/Comparador'))
const Fuentes = lazy(() => import('./pages/Fuentes'))
const Guia = lazy(() => import('./pages/Guia'))
const Laboratorio = lazy(() => import('./pages/Laboratorio'))
const Login = lazy(() => import('./pages/Login'))
const ObraDetalle = lazy(() => import('./pages/ObraDetalle'))
const Obras = lazy(() => import('./pages/Obras'))
const Panorama = lazy(() => import('./pages/Panorama'))
const Sistema = lazy(() => import('./pages/Sistema'))
const Suscribirse = lazy(() => import('./pages/Suscribirse'))

const NAV = [
  {
    grupo: 'Monitoreo',
    items: [
      { to: '/', label: 'Panorama', icono: LayoutDashboard, end: true },
      { to: '/obras', label: 'Alertas del cuaderno', icono: FileText },
      { to: '/cartera', label: 'Cartera nacional', icono: Building2 },
      { to: '/comparador', label: 'Comparador', icono: BarChart3 },
    ],
  },
  {
    grupo: 'Evidencia',
    items: [
      { to: '/laboratorio', label: 'Validación del modelo', icono: ShieldCheck },
      { to: '/fuentes', label: 'Datos y fuentes', icono: Database },
      { to: '/sistema', label: 'Estado y monitoreo', icono: Activity },
    ],
  },
  { grupo: 'Ayuda', items: [{ to: '/guia', label: 'Guía y glosario', icono: BookOpen }] },
]

const ESTADO_TEXTO = { OPERATIVO: 'Operativo', CON_AVISOS: 'Operativo con avisos', DEGRADADO: 'Degradado' } as const
const ESTADO_PUNTO = { OPERATIVO: 'bg-bajo', CON_AVISOS: 'bg-amber-500', DEGRADADO: 'bg-alto' } as const

function Logo({ className = 'size-9' }: { className?: string }) {
  return <img src="/favicon.svg" alt="" className={className} />
}

function Marca({ compacta }: { compacta?: boolean }) {
  return (
    <NavLink to="/" className="flex items-center gap-3 rounded-lg">
      <Logo className={compacta ? 'size-8' : 'size-10'} />
      <span className="leading-tight">
        <span className="block font-display text-lg font-bold tracking-tight text-marca-950">SATO</span>
        {!compacta && <span className="block text-xs font-medium text-slate-600">Alerta temprana de obras públicas</span>}
      </span>
    </NavLink>
  )
}

function Navegacion({ alNavegar }: { alNavegar?: () => void }) {
  const { departamento } = useAmbito()
  const r = useQuery({
    queryKey: ['resumen', departamento],
    queryFn: () => api<{ fecha_corte_cuaderno: string; fecha_corte_cartera: string | null }>(`/resumen${qs({ departamento })}`),
  })
  const estado = useEstado()
  return (
    <div className="flex h-full flex-col">
      <div className="px-5 pt-5 pb-4">
        <Marca />
      </div>
      <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-2" aria-label="Navegación principal">
        {NAV.map((g) => (
          <div key={g.grupo}>
            <div className="etiqueta px-3 pb-2">{g.grupo}</div>
            <ul className="space-y-0.5">
              {g.items.map((n) => (
                <li key={n.to}>
                  <NavLink
                    to={n.to}
                    end={n.end}
                    onClick={alNavegar}
                    className={({ isActive }) =>
                      `relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-[0.95rem] font-semibold transition-colors duration-150 ${
                        isActive
                          ? 'bg-marca-50 text-marca-800 before:absolute before:inset-y-2 before:left-0 before:w-[3px] before:rounded-full before:bg-marca-600'
                          : 'text-slate-700 hover:bg-slate-100 hover:text-slate-900'
                      }`
                    }
                  >
                    <n.icono className="size-[1.15rem] shrink-0" aria-hidden />
                    {n.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>
      <div className="m-3 rounded-xl border border-slate-200 bg-slate-50 p-3.5 text-sm">
        <div className="font-semibold text-slate-900">Datos al corte</div>
        <dl className="mt-1 space-y-0.5 text-slate-600">
          <div className="flex justify-between gap-2">
            <dt>Cuaderno digital</dt>
            <dd className="num font-medium text-slate-800">{r.data ? fmtFecha(r.data.fecha_corte_cuaderno) : '…'}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt>Cartera INFOBRAS</dt>
            <dd className="num font-medium text-slate-800">{r.data ? fmtFecha(r.data.fecha_corte_cartera) : '…'}</dd>
          </div>
        </dl>
        {estado.data && (
          <NavLink to="/sistema" onClick={alNavegar} className="mt-2.5 flex items-center gap-2 border-t border-slate-200 pt-2.5 font-semibold text-marca-800 hover:underline">
            <span className={`size-2.5 rounded-full ${ESTADO_PUNTO[estado.data.estado]}`} aria-hidden />
            Sistema: {ESTADO_TEXTO[estado.data.estado].toLowerCase()}
          </NavLink>
        )}
      </div>
    </div>
  )
}

function Busqueda({ alBuscar, autoFocus }: { alBuscar?: () => void; autoFocus?: boolean }) {
  const nav = useNavigate()
  const [q, setQ] = useState('')
  return (
    <form
      role="search"
      className="relative w-full"
      onSubmit={(e) => {
        e.preventDefault()
        if (q.trim()) {
          nav(`/buscar?q=${encodeURIComponent(q.trim())}`)
          alBuscar?.()
        }
      }}
    >
      <Search className="pointer-events-none absolute top-1/2 left-3 size-[1.1rem] -translate-y-1/2 text-slate-500" aria-hidden />
      <input
        className="entrada w-full pl-10"
        type="search"
        enterKeyHint="search"
        placeholder="Buscar obra, entidad, CUI o código INFOBRAS"
        aria-label="Buscar obras"
        maxLength={120}
        value={q}
        autoFocus={autoFocus}
        onChange={(e) => setQ(e.target.value)}
      />
    </form>
  )
}

function BarraSuperior({ abrirMenu }: { abrirMenu: () => void }) {
  const { usuario, logout } = useAuth()
  const { departamento, setDepartamento, opciones } = useAmbito()
  const { pathname } = useLocation()
  // el buscador del teléfono queda abierto solo en la pantalla donde se abrió
  const [abiertoEn, setAbiertoEn] = useState<string | null>(null)
  const buscando = abiertoEn === pathname
  return (
    <header role="banner" style={{ zIndex: 'var(--z-cabecera)' }} className="sticky top-0 border-b border-slate-200 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/85">
      <div className="flex h-16 items-center gap-2 px-3 sm:gap-3 sm:px-6">
        <button className="btn-fantasma size-10 p-0 lg:hidden" onClick={abrirMenu} aria-label="Abrir menú">
          <Menu className="size-5" />
        </button>
        <div className="lg:hidden">
          <Marca compacta />
        </div>
        <div className="hidden max-w-xl flex-1 md:block">
          <Busqueda />
        </div>
        <div className="flex-1 md:hidden" />
        <button className="btn-fantasma size-10 p-0 md:hidden" onClick={() => setAbiertoEn(buscando ? null : pathname)} aria-label={buscando ? 'Cerrar búsqueda' : 'Buscar'} aria-expanded={buscando}>
          {buscando ? <X className="size-5" /> : <Search className="size-5" />}
        </button>
        <label className="hidden items-center gap-2 sm:flex">
          <MapPin className="size-4 text-slate-500" aria-hidden />
          <span className="sr-only">Ámbito geográfico</span>
          <select className="entrada max-w-44 xl:max-w-56" value={departamento ?? ''} onChange={(e) => setDepartamento(e.target.value || null)} aria-label="Ámbito geográfico">
            <option value="">Todo el Perú</option>
            {opciones.map((o) => (
              <option key={o.departamento} value={o.departamento}>
                {titulo(o.departamento)}
              </option>
            ))}
          </select>
        </label>
        <NavLink to="/suscribirse" className="btn-primario hidden lg:inline-flex">
          <Mail className="size-4" aria-hidden />
          Recibir alertas
        </NavLink>
        {usuario ? (
          <button onClick={logout} className="btn-fantasma" title={usuario.email}>
            <LogOut className="size-4" aria-hidden />
            <span className="hidden sm:inline">Salir</span>
            <span className="sr-only sm:hidden">Salir</span>
          </button>
        ) : (
          <NavLink to="/login" className="btn-fantasma" aria-label="Ingresar (analistas)">
            <LogIn className="size-4" aria-hidden />
            <span className="hidden sm:inline">Ingresar</span>
          </NavLink>
        )}
      </div>
      {buscando && (
        <div className="space-y-2 border-t border-slate-100 px-3 py-3 md:hidden">
          <Busqueda autoFocus alBuscar={() => setAbiertoEn(null)} />
          <select className="entrada w-full sm:hidden" value={departamento ?? ''} onChange={(e) => setDepartamento(e.target.value || null)} aria-label="Ámbito geográfico (teléfono)">
            <option value="">Todo el Perú</option>
            {opciones.map((o) => (
              <option key={o.departamento} value={o.departamento}>
                {titulo(o.departamento)}
              </option>
            ))}
          </select>
        </div>
      )}
    </header>
  )
}

const PORTALES = [
  { l: 'Plataforma Nacional de Datos Abiertos', u: 'https://www.datosabiertos.gob.pe' },
  { l: 'OECE: CONOSCE y cuaderno de obra digital', u: 'https://conosce.osce.gob.pe' },
  { l: 'MEF: datos abiertos (Invierte.pe, SIAF)', u: 'https://datosabiertos.mef.gob.pe' },
  { l: 'Contraloría: INFOBRAS', u: 'https://infobras.contraloria.gob.pe' },
]

function Pie() {
  return (
    <footer className="mt-10 border-t border-slate-200 bg-white">
      <div className="mx-auto grid max-w-[1440px] grid-cols-1 gap-8 px-4 py-8 text-sm text-slate-600 sm:px-6 md:grid-cols-3 lg:px-8">
        <div>
          <div className="flex items-center gap-2.5">
            <Logo className="size-8" />
            <span className="font-display text-base font-bold text-marca-950">SATO</span>
          </div>
          <p className="mt-3 leading-relaxed">
            Sistema de alerta temprana de atraso en obras públicas construido solo con datos abiertos oficiales. Las estimaciones son probabilísticas: sirven para priorizar la supervisión y no
            determinan responsabilidades de ninguna entidad, funcionario o contratista.
          </p>
        </div>
        <div>
          <h2 className="etiqueta">Fuentes oficiales</h2>
          <ul className="mt-3 space-y-2">
            {PORTALES.map((p) => (
              <li key={p.u}>
                <a href={p.u} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 font-medium text-marca-700 hover:text-marca-900 hover:underline">
                  {p.l}
                  <ExternalLink className="size-3.5" aria-hidden />
                  <span className="sr-only">(se abre en otra pestaña)</span>
                </a>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h2 className="etiqueta">Transparencia del sistema</h2>
          <ul className="mt-3 space-y-2">
            <li>
              <NavLink to="/laboratorio" className="font-medium text-marca-700 hover:underline">
                Cómo se validó el modelo
              </NavLink>
            </li>
            <li>
              <NavLink to="/fuentes" className="font-medium text-marca-700 hover:underline">
                Archivos fuente y auditoría de calidad
              </NavLink>
            </li>
            <li>
              <NavLink to="/sistema" className="font-medium text-marca-700 hover:underline">
                Estado de la plataforma
              </NavLink>
            </li>
            <li>
              <a href="/api/docs" className="font-medium text-marca-700 hover:underline">
                API pública y su documentación
              </a>
            </li>
          </ul>
        </div>
      </div>
      <div className="border-t border-slate-100">
        <p className="mx-auto max-w-[1440px] px-4 py-4 text-xs text-slate-600 sm:px-6 lg:px-8">
          Prototipo de investigación académica (tesis de Ingeniería de Sistemas). No es un sitio oficial de ninguna entidad del Estado peruano.
        </p>
      </div>
    </footer>
  )
}

function Pagina({ children }: { children: ReactNode }) {
  const { pathname } = useLocation()
  const [inicial] = useState(pathname)
  useEffect(() => {
    // al cambiar de pantalla, el foco pasa al contenido (lectores de pantalla); no en la carga inicial
    if (pathname !== inicial) document.getElementById('contenido')?.focus({ preventScroll: true })
  }, [pathname, inicial])
  return (
    <LimiteDeError key={pathname}>
      <div className="animate-aparecer">
        <Suspense fallback={<CargandoPagina />}>{children}</Suspense>
      </div>
    </LimiteDeError>
  )
}

export default function App() {
  const [menu, setMenu] = useState(false)
  return (
    <div className="min-h-screen">
      <a
        href="#contenido"
        style={{ zIndex: 'var(--z-salto)' }}
        className="sr-only rounded-md bg-white px-4 py-2.5 text-sm font-semibold text-marca-800 shadow-lg ring-2 ring-marca-600 focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
      >
        Saltar al contenido principal
      </a>
      <div className="no-imprimir bg-marca-950 text-marca-100">
        <p className="mx-auto flex max-w-[1600px] items-center gap-2 px-4 py-1.5 text-xs sm:px-6">
          <span className="font-semibold text-white">Prototipo de investigación</span>
          <span aria-hidden>·</span>
          <span className="hidden truncate sm:inline">Construido con datos abiertos del Estado peruano; no es un sitio oficial de ninguna entidad pública.</span>
          <span className="truncate sm:hidden">No es un sitio oficial del Estado.</span>
        </p>
      </div>
      <div className="flex">
        <aside style={{ zIndex: 'var(--z-lateral)' }} className="sticky top-0 hidden h-screen w-72 shrink-0 border-r border-slate-200 bg-white lg:block">
          <Navegacion />
        </aside>
        <Dialog.Root open={menu} onOpenChange={setMenu}>
          <Dialog.Portal>
            <Dialog.Overlay style={{ zIndex: 'var(--z-capa)' }} className="fixed inset-0 bg-slate-900/40 lg:hidden" />
            <Dialog.Content style={{ zIndex: 'var(--z-dialogo)' }} className="fixed inset-y-0 left-0 w-80 max-w-[88vw] animate-aparecer bg-white shadow-2xl lg:hidden">
              <Dialog.Title className="sr-only">Menú</Dialog.Title>
              <Dialog.Description className="sr-only">Navegación principal de SATO</Dialog.Description>
              <Dialog.Close className="btn-fantasma absolute top-4 right-3 size-10 p-0" aria-label="Cerrar menú">
                <X className="size-5" />
              </Dialog.Close>
              <Navegacion alNavegar={() => setMenu(false)} />
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>
        <div className="flex min-w-0 flex-1 flex-col">
          <BarraSuperior abrirMenu={() => setMenu(true)} />
          <main id="contenido" tabIndex={-1} className="mx-auto min-h-[calc(100vh-4rem)] w-full max-w-[1440px] flex-1 px-4 py-6 outline-none sm:px-6 lg:px-8 lg:py-8">
            <Pagina>
              <Routes>
                <Route path="/" element={<Panorama />} />
                <Route path="/buscar" element={<Buscar />} />
                <Route path="/cartera" element={<Cartera />} />
                <Route path="/cartera/:codigo" element={<CarteraDetalle />} />
                <Route path="/obras" element={<Obras />} />
                <Route path="/obras/:id" element={<ObraDetalle />} />
                <Route path="/comparador" element={<Comparador />} />
                <Route path="/laboratorio" element={<Laboratorio />} />
                <Route path="/modelo" element={<Navigate to="/laboratorio" replace />} />
                <Route path="/alertas" element={<Navigate to="/obras?nivel=ALTO" replace />} />
                <Route path="/fuentes" element={<Fuentes />} />
                <Route path="/sistema" element={<Sistema />} />
                <Route path="/guia" element={<Guia />} />
                <Route path="/suscribirse" element={<Suscribirse />} />
                <Route path="/login" element={<Login />} />
                <Route
                  path="*"
                  element={
                    <div className="tarjeta">
                      <Vacio
                        titulo="Página no encontrada"
                        texto="La dirección no existe o fue movida."
                        accion={
                          <NavLink to="/" className="btn">
                            Ir al panorama
                          </NavLink>
                        }
                      />
                    </div>
                  }
                />
              </Routes>
            </Pagina>
          </main>
          <Pie />
        </div>
      </div>
    </div>
  )
}
