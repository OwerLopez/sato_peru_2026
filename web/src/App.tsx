import { NavLink, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth'
import Alertas from './pages/Alertas'
import Dashboard from './pages/Dashboard'
import Fuentes from './pages/Fuentes'
import Login from './pages/Login'
import Modelo from './pages/Modelo'
import ObraDetalle from './pages/ObraDetalle'
import Obras from './pages/Obras'

const nav = [
  { to: '/', label: 'Panel', end: true },
  { to: '/alertas', label: 'Alertas' },
  { to: '/obras', label: 'Obras' },
  { to: '/modelo', label: 'Modelo y validación' },
  { to: '/fuentes', label: 'Datos y fuentes' },
]

export default function App() {
  const { usuario, logout } = useAuth()
  return (
    <div className="flex min-h-full flex-col">
      <header className="bg-marca-800 text-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <NavLink to="/" className="flex items-center gap-2">
            <img src="/favicon.svg" alt="" className="h-7 w-7" />
            <div className="leading-tight">
              <div className="font-bold tracking-tight">SATO-AQP</div>
              <div className="text-[11px] text-marca-100">Alerta temprana de obras públicas · Arequipa</div>
            </div>
          </NavLink>
          <nav className="flex flex-wrap gap-1 text-sm">
            {nav.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => `rounded-md px-3 py-1.5 ${isActive ? 'bg-white/15 font-semibold' : 'text-marca-100 hover:bg-white/10'}`}>
                {n.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto text-sm">
            {usuario ? (
              <span className="flex items-center gap-2">
                <span className="text-marca-100">
                  {usuario.nombre} · {usuario.rol}
                </span>
                <button onClick={logout} className="rounded-md bg-white/10 px-2 py-1 hover:bg-white/20">
                  Salir
                </button>
              </span>
            ) : (
              <NavLink to="/login" className="rounded-md bg-white/10 px-3 py-1.5 hover:bg-white/20">
                Ingresar
              </NavLink>
            )}
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-5">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/alertas" element={<Alertas />} />
          <Route path="/obras" element={<Obras />} />
          <Route path="/obras/:id" element={<ObraDetalle />} />
          <Route path="/modelo" element={<Modelo />} />
          <Route path="/fuentes" element={<Fuentes />} />
          <Route path="/login" element={<Login />} />
          <Route path="*" element={<div className="tarjeta p-6">Página no encontrada.</div>} />
        </Routes>
      </main>
      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto max-w-7xl px-4 py-3 text-xs text-slate-500">
          Datos abiertos oficiales: OECE (cuaderno de obra digital, SEACE), MEF (Invierte.pe, SIAF), Contraloría (INFOBRAS, obras paralizadas). Las alertas son
          estimaciones probabilísticas para priorizar la supervisión; no constituyen una determinación de responsabilidad. Tesis de Ingeniería de Sistemas – UNSA.
        </div>
      </footer>
    </div>
  )
}
