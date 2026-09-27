import { Search } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { EncabezadoPagina, Seccion } from '../components/ui'
import { GLOSARIO } from '../glosario'

const PASOS = [
  { t: 'Elija su ámbito', d: 'Con el selector «Ámbito» de la barra superior vea todo el Perú o un departamento. Todas las pantallas se filtran automáticamente.' },
  { t: 'Revise el panorama', d: 'La portada resume cuántas obras en ejecución tienen riesgo alto y cuáles requieren atención primero. Seleccione una obra para ver por qué.' },
  { t: 'Abra la ficha de la obra', d: 'Verá el nivel de riesgo, su confiabilidad, los factores que lo elevan en lenguaje claro y la evidencia oficial que los respalda (asientos, gasto, seguimiento).' },
  { t: 'Descargue el informe', d: 'El botón «Informe técnico PDF» genera un documento con los datos de la obra, el riesgo, los factores, la evidencia y el marco normativo.' },
  { t: 'Registre su revisión', d: 'Si ingresa como analista puede marcar cada alerta como confirmada, descartada o en seguimiento; queda en el registro de auditoría.' },
  { t: 'Reciba alertas', d: 'Con «Recibir alertas» se suscribe a un resumen semanal por correo de las obras de su ámbito que pasan a riesgo alto.' },
]

export default function Guia() {
  const [q, setQ] = useState('')
  const t = q.trim().toLowerCase()
  const terminos = Object.values(GLOSARIO)
    .filter((g) => !t || g.termino.toLowerCase().includes(t) || g.definicion.toLowerCase().includes(t))
    .sort((a, b) => a.termino.localeCompare(b.termino, 'es'))
  return (
    <div className="space-y-5">
      <EncabezadoPagina titulo="Guía y glosario" descripcion="SATO ayuda a decidir qué obras supervisar primero, con estimaciones explicadas y evidencia verificable en fuentes oficiales." />
      <ol className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {PASOS.map((p, i) => (
          <li key={p.t} className="tarjeta flex gap-3 p-4">
            <span className="num flex size-7 shrink-0 items-center justify-center rounded-full bg-marca-50 text-sm font-semibold text-marca-700">{i + 1}</span>
            <div>
              <div className="font-medium text-slate-900">{p.t}</div>
              <p className="mt-1 text-sm leading-relaxed text-slate-600">{p.d}</p>
            </div>
          </li>
        ))}
      </ol>
      <div className="grid gap-5 lg:grid-cols-3">
        <Seccion
          titulo="Glosario"
          className="lg:col-span-2"
          accion={
            <div className="relative">
              <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-slate-400" />
              <input className="entrada h-8 w-56 pl-8" placeholder="Buscar un término" aria-label="Buscar en el glosario" value={q} onChange={(e) => setQ(e.target.value)} />
            </div>
          }
        >
          <dl className="grid gap-x-6 gap-y-4 md:grid-cols-2">
            {terminos.map((g) => (
              <div key={g.termino}>
                <dt className="text-sm font-medium text-slate-900">{g.termino}</dt>
                <dd className="mt-0.5 text-sm leading-relaxed text-slate-600">{g.definicion}</dd>
              </div>
            ))}
            {terminos.length === 0 && <p className="text-sm text-slate-500">Ningún término coincide con la búsqueda.</p>}
          </dl>
        </Seccion>
        <Seccion titulo="Qué puede y qué no puede hacer">
          <ul className="space-y-3 text-sm leading-relaxed text-slate-700">
            <li>
              <b className="text-slate-900">Puede:</b> ordenar las obras por su probabilidad de atraso, con desempeño medido en periodos posteriores al entrenamiento (ver{' '}
              <Link to="/laboratorio" className="enlace">
                Validación del modelo
              </Link>
              ).
            </li>
            <li>
              <b className="text-slate-900">No puede:</b> determinar responsabilidades ni reemplazar la verificación en campo. Una alerta es un indicio para revisar, no una conclusión.
            </li>
            <li>
              <b className="text-slate-900">Depende de:</b> lo que las entidades registran en las fuentes oficiales. Las limitaciones conocidas están en{' '}
              <Link to="/fuentes" className="enlace">
                Datos y fuentes
              </Link>
              .
            </li>
          </ul>
        </Seccion>
      </div>
    </div>
  )
}
