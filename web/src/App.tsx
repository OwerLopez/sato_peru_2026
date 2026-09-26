import { useState } from 'react'
import { Navigate, NavLink, Route, Routes } from 'react-router-dom'
import { useAmbito } from './ambito'
import { useAuth } from './auth'
import Cartera from './pages/Cartera'
import CarteraDetalle from './pages/CarteraDetalle'
import Comparador from './pages/Comparador'
import Fuentes from './pages/Fuentes'
import Guia from './pages/Guia'
import Laboratorio from './pages/Laboratorio'
import Login from './pages/Login'
import ObraDetalle from './pages/ObraDetalle'
import Obras from './pages/Obras'
import Radar from './pages/Radar'
import Suscribirse from './pages/Suscribirse'

const nav = [
  { to: '/', label: 'Radar', end: true },
  { to: '/cartera', label: 'Cartera nacional' },
  { to: '/obras', label: 'Cuadernos de obra' },
  { to: '/comparador', label: 'Comparador' },
  { to: '/laboratorio', label: 'Laboratorio de validación' },
  { to: '/fuentes', label: 'Datos y sistema' },
  { to: '/guia', label: 'Guía' },
]

export default function App() {
  const { usuario, logout } = useAuth()
  const { departamento, setDepartamento, opciones } = useAmbito()
  const [menu, setMenu] = useState(false)
  return (
    <div className="flex min-h-full flex-col">
      <header className="sticky top-0 z-[1000] bg-marca-900 text-white shadow">
        <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-x-5 gap-y-2 px-4 py-2.5">
          <NavLink to="/" className="flex items-center gap-2">
            <img src="/favicon.svg" alt="" className="h-8 w-8" />
            <div className="leading-tight">
              <div className="text-lg font-bold tracking-tight">SATO</div>
              <div className="text-[11px] text-marca-100">Sistema de Alerta Temprana de Obras Públicas</div>
            </div>
          </NavLink>
          <button className="ml-auto rounded-md bg-white/10 px-2 py-1 text-sm lg:hidden" onClick={() => setMenu(!menu)} aria-label="Menú">
            Menú
          </button>
          <nav className={`${menu ? 'flex' : 'hidden'} w-full flex-col gap-1 text-sm lg:flex lg:w-auto lg:flex-row`}>
            {nav.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                onClick={() => setMenu(false)}
                className={({ isActive }) => `rounded-md px-3 py-1.5 ${isActive ? 'bg-white/15 font-semibold' : 'text-marca-100 hover:bg-white/10'}`}
              >
                {n.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex flex-wrap items-center gap-2 text-sm">
            <label className="flex items-center gap-2">
              <span className="text-marca-100">Ámbito</span>
              <select
                value={departamento ?? ''}
                onChange={(e) => setDepartamento(e.target.value || null)}
                className="rounded-md border border-white/20 bg-marca-800 px-2 py-1 text-white"
                aria-label="Ámbito geográfico"
              >
                <option value="">Todo el Perú</option>
                {opciones.map((o) => (
                  <option key={o.departamento} value={o.departamento}>
                    {o.departamento}
                  </option>
                ))}
              </select>
            </label>
            <NavLink to="/suscribirse" className="rounded-md bg-amber-400 px-3 py-1 font-semibold text-marca-900 hover:bg-amber-300">
              Recibir alertas
            </NavLink>
            {usuario ? (
              <button onClick={logout} className="rounded-md bg-white/10 px-2 py-1 hover:bg-white/20" title={usuario.email}>
                Salir ({usuario.rol})
              </button>
            ) : (
              <NavLink to="/login" className="rounded-md bg-white/10 px-3 py-1 hover:bg-white/20">
                Ingresar
              </NavLink>
            )}
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-5">
        <Routes>
          <Route path="/" element={<Radar />} />
          <Route path="/cartera" element={<Cartera />} />
          <Route path="/cartera/:codigo" element={<CarteraDetalle />} />
          <Route path="/obras" element={<Obras />} />
          <Route path="/obras/:id" element={<ObraDetalle />} />
          <Route path="/comparador" element={<Comparador />} />
          <Route path="/laboratorio" element={<Laboratorio />} />
          <Route path="/modelo" element={<Navigate to="/laboratorio" replace />} />
          <Route path="/alertas" element={<Navigate to="/" replace />} />
          <Route path="/fuentes" element={<Fuentes />} />
          <Route path="/guia" element={<Guia />} />
          <Route path="/suscribirse" element={<Suscribirse />} />
          <Route path="/login" element={<Login />} />
          <Route path="*" element={<div className="tarjeta p-6">Página no encontrada.</div>} />
        </Routes>
      </main>
      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto max-w-[1400px] px-4 py-3 text-xs text-slate-500">
          Datos abiertos oficiales: OECE (cuaderno de obra digital, SEACE), MEF (Invierte.pe, SIAF) y Contraloría General de la República (INFOBRAS,
          obras paralizadas). Las estimaciones son probabilísticas y sirven para priorizar la supervisión; no constituyen determinación de
          responsabilidad de ninguna entidad o contratista.
        </div>
      </footer>
    </div>
  )
}
