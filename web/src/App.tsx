import { useQuery } from '@tanstack/react-query'
import { BarChart3, BookOpen, Building2, Database, FileText, LayoutDashboard, LogIn, LogOut, Mail, Menu, Search, ShieldCheck, X } from 'lucide-react'
import { Dialog } from 'radix-ui'
import { lazy, Suspense, useState, type ReactNode } from 'react'
import { Navigate, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { api, fmtFecha, qs } from './api'
import { useAmbito } from './ambito'
import { useAuth } from './auth'
import { CargandoPagina, Vacio } from './components/ui'

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
    ],
  },
  { grupo: 'Ayuda', items: [{ to: '/guia', label: 'Guía y glosario', icono: BookOpen }] },
]

function Marca() {
  return (
    <NavLink to="/" className="flex items-center gap-2.5 px-2">
      <img src="/favicon.svg" alt="" className="size-8" />
      <div className="leading-tight">
        <div className="text-[15px] font-semibold tracking-tight text-white">SATO</div>
        <div className="text-[11px] text-marca-200">Alerta temprana de obras públicas</div>
      </div>
    </NavLink>
  )
}

function Navegacion({ alNavegar }: { alNavegar?: () => void }) {
  const { departamento } = useAmbito()
  const r = useQuery({
    queryKey: ['resumen', departamento],
    queryFn: () => api<{ fecha_corte_cuaderno: string; fecha_corte_cartera: string | null }>(`/resumen${qs({ departamento })}`),
  })
  return (
    <div className="flex h-full flex-col gap-6 py-4">
      <Marca />
      <nav className="flex-1 space-y-5 px-2" aria-label="Navegación principal">
        {NAV.map((g) => (
          <div key={g.grupo}>
            <div className="px-2 pb-1.5 text-[11px] font-semibold tracking-[0.08em] text-marca-200/80 uppercase">{g.grupo}</div>
            <ul className="space-y-0.5">
              {g.items.map((n) => (
                <li key={n.to}>
                  <NavLink
                    to={n.to}
                    end={n.end}
                    onClick={alNavegar}
                    className={({ isActive }) =>
                      `flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors ${isActive ? 'bg-white/12 font-medium text-white' : 'text-marca-100 hover:bg-white/8 hover:text-white'}`
                    }
                  >
                    <n.icono className="size-4 shrink-0 opacity-90" />
                    {n.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>
      <div className="mx-4 rounded-lg bg-white/6 p-3 text-[11px] leading-relaxed text-marca-100">
        <div className="font-semibold text-white">Datos al corte</div>
        <div>Cuaderno digital: {r.data ? fmtFecha(r.data.fecha_corte_cuaderno) : '…'}</div>
        <div>Cartera INFOBRAS: {r.data ? fmtFecha(r.data.fecha_corte_cartera) : '…'}</div>
      </div>
    </div>
  )
}

function BarraSuperior({ abrirMenu }: { abrirMenu: () => void }) {
  const { usuario, logout } = useAuth()
  const { departamento, setDepartamento, opciones } = useAmbito()
  const nav = useNavigate()
  const [q, setQ] = useState('')
  return (
    <header className="sticky top-0 z-[1000] border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="flex h-14 items-center gap-2 px-3 sm:gap-3 sm:px-5">
        <button className="btn-fantasma size-9 p-0 lg:hidden" onClick={abrirMenu} aria-label="Abrir menú">
          <Menu className="size-5" />
        </button>
        <form
          role="search"
          className="relative min-w-0 flex-1 sm:max-w-md"
          onSubmit={(e) => {
            e.preventDefault()
            if (q.trim()) nav(`/buscar?q=${encodeURIComponent(q.trim())}`)
          }}
        >
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" />
          <input className="entrada w-full pl-9" placeholder="Buscar obra, entidad, CUI o código INFOBRAS" aria-label="Buscar obras" maxLength={120} value={q} onChange={(e) => setQ(e.target.value)} />
        </form>
        <label className="flex items-center gap-2 text-sm">
          <span className="hidden text-slate-500 xl:inline">Ámbito</span>
          <select className="entrada max-w-40 sm:max-w-52" value={departamento ?? ''} onChange={(e) => setDepartamento(e.target.value || null)} aria-label="Ámbito geográfico">
            <option value="">Todo el Perú</option>
            {opciones.map((o) => (
              <option key={o.departamento} value={o.departamento}>
                {o.departamento.charAt(0) + o.departamento.slice(1).toLowerCase()}
              </option>
            ))}
          </select>
        </label>
        <NavLink to="/suscribirse" className="btn-primario hidden md:inline-flex">
          <Mail className="size-4" />
          Recibir alertas
        </NavLink>
        {usuario ? (
          <button onClick={logout} className="btn-fantasma" title={usuario.email}>
            <LogOut className="size-4" />
            <span className="hidden sm:inline">Salir</span>
          </button>
        ) : (
          <NavLink to="/login" className="btn-fantasma">
            <LogIn className="size-4" />
            <span className="hidden sm:inline">Ingresar</span>
          </NavLink>
        )}
      </div>
    </header>
  )
}

function Pagina({ children }: { children: ReactNode }) {
  const { pathname } = useLocation()
  return (
    <div key={pathname} className="animate-aparecer">
      <Suspense fallback={<CargandoPagina />}>{children}</Suspense>
    </div>
  )
}

export default function App() {
  const [menu, setMenu] = useState(false)
  return (
    <div className="flex min-h-full">
      <aside className="fixed inset-y-0 left-0 z-[1100] hidden w-64 bg-marca-950 lg:block">
        <Navegacion />
      </aside>
      <Dialog.Root open={menu} onOpenChange={setMenu}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-[1500] bg-slate-900/40 lg:hidden" />
          <Dialog.Content className="fixed inset-y-0 left-0 z-[1600] w-72 max-w-[85vw] bg-marca-950 lg:hidden">
            <Dialog.Title className="sr-only">Menú</Dialog.Title>
            <Dialog.Description className="sr-only">Navegación principal de SATO</Dialog.Description>
            <Dialog.Close className="absolute top-4 right-3 rounded-md p-1.5 text-marca-100 hover:bg-white/10" aria-label="Cerrar menú">
              <X className="size-5" />
            </Dialog.Close>
            <Navegacion alNavegar={() => setMenu(false)} />
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
      <div className="flex min-w-0 flex-1 flex-col lg:pl-64">
        <BarraSuperior abrirMenu={() => setMenu(true)} />
        <main className="mx-auto w-full max-w-[1440px] flex-1 px-3 py-5 sm:px-5 lg:px-7 lg:py-6">
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
              <Route path="/guia" element={<Guia />} />
              <Route path="/suscribirse" element={<Suscribirse />} />
              <Route path="/login" element={<Login />} />
              <Route
                path="*"
                element={
                  <div className="tarjeta">
                    <Vacio titulo="Página no encontrada" texto="La dirección no existe o fue movida." accion={<NavLink to="/" className="btn">Ir al panorama</NavLink>} />
                  </div>
                }
              />
            </Routes>
          </Pagina>
        </main>
        <footer className="border-t border-slate-200 bg-white/60">
          <div className="mx-auto max-w-[1440px] px-3 py-3 text-xs leading-relaxed text-slate-500 sm:px-5 lg:px-7">
            Fuentes: datos abiertos del OECE (cuaderno de obra digital, SEACE), del MEF (Invierte.pe, SIAF) y de la Contraloría General de la República (INFOBRAS,
            obras paralizadas). Las estimaciones son probabilísticas y sirven para priorizar la supervisión; no determinan responsabilidades de ninguna entidad o
            contratista.
          </div>
        </footer>
      </div>
    </div>
  )
}
