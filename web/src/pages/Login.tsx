import { LogIn } from 'lucide-react'
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
    <div className="mx-auto mt-6 max-w-sm sm:mt-12">
      <form
        className="tarjeta space-y-4 p-6"
        onSubmit={async (e) => {
          e.preventDefault()
          setError(null)
          setCargando(true)
          try {
            await login(email, password)
            nav('/obras?nivel=ALTO')
          } catch (err) {
            setError((err as Error).message === 'Debe ingresar para realizar esta acción.' ? 'Correo o contraseña incorrectos.' : (err as Error).message)
          } finally {
            setCargando(false)
          }
        }}
      >
        <div>
          <h1 className="text-lg font-semibold text-slate-900">Ingreso de analistas</h1>
          <p className="mt-1 text-sm text-slate-500">La consulta de datos es pública. El ingreso solo es necesario para registrar revisiones de alertas.</p>
        </div>
        <label className="block">
          <span className="text-sm font-medium text-slate-700">Correo</span>
          <input className="entrada mt-1 w-full" type="email" autoComplete="username" required maxLength={200} value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-slate-700">Contraseña</span>
          <input className="entrada mt-1 w-full" type="password" autoComplete="current-password" required maxLength={200} value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && (
          <p className="rounded-lg bg-alto-suave px-3 py-2 text-sm text-red-800" role="alert">
            {error}
          </p>
        )}
        <button className="btn-primario w-full" disabled={cargando}>
          <LogIn className="size-4" />
          {cargando ? 'Ingresando…' : 'Ingresar'}
        </button>
      </form>
    </div>
  )
}
