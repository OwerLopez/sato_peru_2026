import { CheckCircle2, Mail } from 'lucide-react'
import { useState } from 'react'
import { api, titulo } from '../api'
import { useAmbito } from '../ambito'
import { EncabezadoPagina } from '../components/ui'

export default function Suscribirse() {
  const { departamento, opciones } = useAmbito()
  const [email, setEmail] = useState('')
  const [dep, setDep] = useState(departamento ?? '')
  const [prov, setProv] = useState('')
  const [estado, setEstado] = useState<{ ok: boolean; texto: string } | null>(null)
  const [enviando, setEnviando] = useState(false)
  return (
    <div className="mx-auto max-w-xl space-y-4">
      <EncabezadoPagina
        titulo="Recibir alertas por correo"
        descripcion="Cada semana recibirá las obras de su ámbito que pasan a riesgo alto. Debe confirmar su correo y puede darse de baja en cualquier momento desde el enlace de cada mensaje."
      />
      <form
        className="tarjeta space-y-4 p-5"
        onSubmit={async (e) => {
          e.preventDefault()
          setEnviando(true)
          setEstado(null)
          try {
            const r = await api<{ estado: string; mensaje: string }>('/suscripciones', {
              method: 'POST',
              body: JSON.stringify({ email, departamento: dep || null, provincia: prov.trim().toUpperCase() || null }),
            })
            setEstado({ ok: true, texto: r.mensaje })
          } catch (err) {
            setEstado({ ok: false, texto: (err as Error).message })
          } finally {
            setEnviando(false)
          }
        }}
      >
        <label className="block">
          <span className="text-sm font-medium text-slate-700">Correo electrónico</span>
          <input className="entrada mt-1 w-full" type="email" required maxLength={254} autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Departamento</span>
            <select className="entrada mt-1 w-full" value={dep} onChange={(e) => setDep(e.target.value)}>
              <option value="">Todo el Perú</option>
              {opciones.map((o) => (
                <option key={o.departamento} value={o.departamento}>
                  {titulo(o.departamento)}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Provincia (opcional)</span>
            <input className="entrada mt-1 w-full" maxLength={60} value={prov} onChange={(e) => setProv(e.target.value)} placeholder="p. ej.: Caylloma" />
          </label>
        </div>
        <button className="btn-primario" disabled={enviando}>
          <Mail className="size-4" />
          {enviando ? 'Registrando…' : 'Suscribirme'}
        </button>
        {estado && (
          <p className={`flex items-start gap-2 rounded-lg px-3 py-2 text-sm ${estado.ok ? 'bg-bajo-suave text-green-900' : 'bg-alto-suave text-red-800'}`} role="status">
            {estado.ok && <CheckCircle2 className="mt-0.5 size-4 shrink-0" />}
            {estado.texto}
          </p>
        )}
        <p className="text-xs leading-relaxed text-slate-500">
          Solo se almacena su correo y el ámbito elegido, con la finalidad exclusiva de enviar este resumen (Ley N.° 29733, Ley de Protección de Datos Personales).
        </p>
      </form>
    </div>
  )
}
