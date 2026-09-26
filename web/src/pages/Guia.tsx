import { Link } from 'react-router-dom'
import { Seccion } from '../components/ui'

const pasos = [
  { t: '1. Elija su ámbito', d: 'Use el selector "Ámbito" del encabezado para ver todo el Perú o un departamento. Todas las pantallas se filtran automáticamente.' },
  {
    t: '2. Revise el Radar',
    d: 'La portada muestra solo obras en ejecución y lo que el modelo estima que ocurrirá. Empiece por las obras en nivel ALTO de la pestaña "Alerta a 60 días".',
  },
  {
    t: '3. Abra una obra y lea el porqué',
    d: 'Cada obra muestra los factores que elevan o reducen su riesgo (TreeSHAP) y los asientos reales del cuaderno de obra que los sustentan, con su número, fecha y archivo oficial de origen.',
  },
  { t: '4. Descargue el informe', d: 'El botón "Descargar informe técnico (PDF)" genera un documento con los datos, el riesgo, los factores, la evidencia y el marco normativo.' },
  { t: '5. Registre su revisión', d: 'Si ingresa como analista puede marcar cada alerta como confirmada, descartada o en seguimiento; queda en el registro de auditoría.' },
  { t: '6. Reciba alertas', d: 'Con "Recibir alertas" se suscribe a un resumen semanal por correo de las obras de su ámbito que entran a nivel alto.' },
]

const glosario = [
  ['Atraso formal (causal del 80%)', 'Asiento del cuaderno de obra que registra que la valorización acumulada ejecutada es menor al 80% de la programada o que se ordena un calendario acelerado (RLCE art. 203; RLGCP art. 207).'],
  ['Retraso significativo al término', 'La obra culmina después de su fecha programada original más el 30% del plazo original (definición usada para la cartera INFOBRAS).'],
  ['Nivel ALTO / MEDIO / BAJO', 'Tramos de la probabilidad estimada. En el cuaderno digital, ALTO usa el umbral que maximiza F1 en validación; en la cartera, ALTO corresponde al 20% de mayor riesgo.'],
  ['TreeSHAP', 'Método que reparte la predicción entre las variables; indica cuánto sube o baja el riesgo cada factor para esa obra concreta.'],
  ['Backtest as-of', 'Simulación del pasado: en cada fecha el modelo solo usa información que existía en esa fecha y luego se compara con lo que ocurrió.'],
  ['Simulador de sensibilidad', 'Recalcula la probabilidad cambiando una señal a la vez. Muestra de qué depende la estimación; no es un efecto causal garantizado.'],
]

export default function Guia() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-marca-900">Guía de uso</h1>
        <p className="text-sm text-slate-600">SATO ayuda a decidir qué obras supervisar primero, con predicciones explicadas y evidencia verificable en fuentes oficiales.</p>
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {pasos.map((p) => (
          <div key={p.t} className="tarjeta p-4">
            <div className="font-semibold text-marca-800">{p.t}</div>
            <p className="mt-1 text-sm text-slate-600">{p.d}</p>
          </div>
        ))}
      </div>
      <Seccion titulo="Glosario">
        <dl className="grid gap-3 md:grid-cols-2">
          {glosario.map(([a, b]) => (
            <div key={a}>
              <dt className="font-medium text-slate-800">{a}</dt>
              <dd className="text-sm text-slate-600">{b}</dd>
            </div>
          ))}
        </dl>
      </Seccion>
      <Seccion titulo="Qué puede y qué no puede hacer el sistema">
        <ul className="list-disc space-y-1 pl-5 text-sm">
          <li>Prioriza la supervisión con probabilidades validadas en periodos futuros al entrenamiento (ver el Laboratorio de validación).</li>
          <li>No determina responsabilidades ni reemplaza la verificación en campo: una alerta es un indicio para revisar, no una conclusión.</li>
          <li>
            Su cobertura depende de lo que las entidades registran en las fuentes oficiales; ver{' '}
            <Link to="/fuentes" className="text-marca-600 underline">
              Datos y sistema
            </Link>{' '}
            para las limitaciones conocidas.
          </li>
        </ul>
      </Seccion>
    </div>
  )
}
