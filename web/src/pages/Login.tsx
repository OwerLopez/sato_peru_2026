import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'

export default function Login() {
  const { login } = useAuth()
  const nav = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [cargando, setCargando] = useState(false)
  return (
    <div className="mx-auto mt-10 max-w-sm">
      <form
        className="tarjeta space-y-3 p-6"
        onSubmit={async (e) => {
          e.preventDefault()
          setError(null)
          setCargando(true)
          try {
            await login(email, password)
            nav('/alertas')
          } catch (err) {
            setError((err as Error).message)
          } finally {
            setCargando(false)
          }
        }}
      >
        <h1 className="text-lg font-bold text-marca-900">Ingreso de analistas</h1>
        <p className="text-xs text-slate-500">La consulta de datos es pública. El ingreso solo es necesario para registrar revisiones de alertas.</p>
        <label className="block text-sm">
          <span className="etiqueta">Correo</span>
          <input className="entrada mt-1 w-full" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="block text-sm">
          <span className="etiqueta">Contraseña</span>
          <input className="entrada mt-1 w-full" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <p className="text-sm text-red-700">{error}</p>}
        <button className="btn-primario w-full justify-center" disabled={cargando}>
          {cargando ? 'Ingresando…' : 'Ingresar'}
        </button>
      </form>
    </div>
  )
}
