import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, CheckCircle2, Mail, MailCheck, MousePointerClick, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { api, titulo } from '../api'
import { useAmbito } from '../ambito'
import { EncabezadoPagina } from '../components/ui'

const PASOS = [
  { i: Mail, t: 'Registre su correo', d: 'Elija todo el Perú, un departamento o una provincia.' },
  { i: MousePointerClick, t: 'Confirme el enlace', d: 'Le enviaremos un enlace de confirmación válido por 7 días.' },
  { i: MailCheck, t: 'Reciba el resumen semanal', d: 'Obras de su ámbito en riesgo alto, con enlace a su ficha y a la evidencia.' },
]

export default function Suscribirse() {
  const { departamento, opciones } = useAmbito()
  const [email, setEmail] = useState('')
  const [dep, setDep] = useState(departamento ?? '')
  const [prov, setProv] = useState('')
  const [estado, setEstado] = useState<{ ok: boolean; texto: string } | null>(null)
  const [enviando, setEnviando] = useState(false)
  const provincias = useQuery({ queryKey: ['provincias', dep], queryFn: () => api<string[]>(`/ambitos/${encodeURIComponent(dep)}/provincias`), enabled: !!dep, staleTime: Infinity })
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <EncabezadoPagina
        titulo="Recibir alertas por correo"
        descripcion="Un resumen semanal con las obras de su ámbito que están en riesgo alto. Es gratuito, requiere confirmar el correo y puede darse de baja desde cualquier mensaje."
      />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
        <form
          className="tarjeta space-y-5 p-5 sm:p-6 lg:col-span-3"
          aria-describedby="privacidad"
          onSubmit={async (e) => {
            e.preventDefault()
            setEnviando(true)
            setEstado(null)
            try {
              const r = await api<{ estado: string; mensaje: string }>('/suscripciones', {
                method: 'POST',
                body: JSON.stringify({ email: email.trim(), departamento: dep || null, provincia: prov || null }),
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
            <span className="font-semibold text-slate-800">Correo electrónico</span>
            <input
              className="entrada mt-1.5 w-full"
              type="email"
              inputMode="email"
              required
              maxLength={254}
              autoComplete="email"
              spellCheck={false}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="nombre@entidad.gob.pe"
            />
          </label>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="font-semibold text-slate-800">Departamento</span>
              <select
                className="entrada mt-1.5 w-full"
                value={dep}
                onChange={(e) => {
                  setDep(e.target.value)
                  setProv('')
                }}
              >
                <option value="">Todo el Perú</option>
                {opciones.map((o) => (
                  <option key={o.departamento} value={o.departamento}>
                    {titulo(o.departamento)}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="font-semibold text-slate-800">Provincia (opcional)</span>
              <select className="entrada mt-1.5 w-full" value={prov} onChange={(e) => setProv(e.target.value)} disabled={!dep || provincias.isLoading}>
                <option value="">{dep ? 'Todas las provincias' : 'Elija primero un departamento'}</option>
                {(provincias.data ?? []).map((p) => (
                  <option key={p} value={p}>
                    {titulo(p)}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <button className="btn-primario w-full sm:w-auto" disabled={enviando}>
            <Mail className="size-4" aria-hidden />
            {enviando ? 'Registrando…' : 'Suscribirme'}
          </button>
          <div aria-live="polite">
            {estado && (
              <p className={`flex items-start gap-2 rounded-lg px-3.5 py-3 text-sm ${estado.ok ? 'bg-bajo-suave text-green-900' : 'bg-alto-suave text-red-900'}`} role={estado.ok ? 'status' : 'alert'}>
                {estado.ok ? <CheckCircle2 className="mt-0.5 size-4 shrink-0" aria-hidden /> : <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />}
                {estado.texto}
              </p>
            )}
          </div>
          <p id="privacidad" className="flex items-start gap-2 border-t border-slate-100 pt-4 text-sm leading-relaxed text-slate-600">
            <ShieldCheck className="mt-0.5 size-4 shrink-0 text-marca-600" aria-hidden />
            Solo se almacena su correo y el ámbito elegido, con la finalidad exclusiva de enviar este resumen (Ley N.° 29733, Ley de Protección de Datos Personales).
          </p>
        </form>
        <aside className="lg:col-span-2" aria-label="Cómo funciona">
          <ol className="space-y-4">
            {PASOS.map((p, i) => (
              <li key={p.t} className="flex gap-3.5">
                <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-marca-50 text-marca-700 ring-1 ring-marca-100">
                  <p.i className="size-5" aria-hidden />
                </span>
                <div>
                  <div className="font-display font-semibold text-slate-900">
                    {i + 1}. {p.t}
                  </div>
                  <p className="mt-0.5 text-sm text-slate-600">{p.d}</p>
                </div>
              </li>
            ))}
          </ol>
        </aside>
      </div>
    </div>
  )
}
