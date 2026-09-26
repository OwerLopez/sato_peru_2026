import { useState } from 'react'
import { api } from '../api'
import { useAmbito } from '../ambito'

export default function Suscribirse() {
  const { departamento, opciones } = useAmbito()
  const [email, setEmail] = useState('')
  const [dep, setDep] = useState(departamento ?? '')
  const [prov, setProv] = useState('')
  const [estado, setEstado] = useState<{ ok: boolean; texto: string } | null>(null)
  const [enviando, setEnviando] = useState(false)
  return (
    <div className="mx-auto max-w-xl space-y-4">
      <div>
        <h1 className="text-xl font-bold text-marca-900">Recibir alertas por correo</h1>
        <p className="text-sm text-slate-600">
          Suscríbase para recibir cada semana las obras de su ámbito que ingresan a nivel alto de riesgo. Se requiere confirmar el correo (doble opción) y puede darse de
          baja en cualquier momento desde el enlace incluido en cada mensaje.
        </p>
      </div>
      <form
        className="tarjeta space-y-3 p-5"
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
        <label className="block text-sm">
          <span className="etiqueta">Correo electrónico</span>
          <input className="entrada mt-1 w-full" type="email" required maxLength={254} value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="block text-sm">
          <span className="etiqueta">Departamento</span>
          <select className="entrada mt-1 w-full" value={dep} onChange={(e) => setDep(e.target.value)}>
            <option value="">Todo el Perú</option>
            {opciones.map((o) => (
              <option key={o.departamento}>{o.departamento}</option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="etiqueta">Provincia (opcional)</span>
          <input className="entrada mt-1 w-full" maxLength={60} value={prov} onChange={(e) => setProv(e.target.value)} placeholder="p.ej. CAYLLOMA" />
        </label>
        <button className="btn-primario" disabled={enviando}>
          {enviando ? 'Registrando…' : 'Suscribirme'}
        </button>
        {estado && <p className={`text-sm ${estado.ok ? 'text-green-700' : 'text-red-700'}`}>{estado.texto}</p>}
        <p className="text-xs text-slate-500">
          Solo se almacena su correo y el ámbito elegido, con la finalidad exclusiva de enviar este resumen (Ley N.° 29733, Ley de Protección de Datos Personales).
        </p>
      </form>
    </div>
  )
}
