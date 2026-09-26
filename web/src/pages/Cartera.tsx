import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, fmtFecha, fmtMillones, fmtPct, qs, type Nivel } from '../api'
import { useAmbito } from '../ambito'
import { Cargando, ErrorMsg, NivelBadge, Paginacion } from '../components/ui'

interface Item {
  codigo_infobras: string
  nombre: string
  departamento: string
  provincia: string
  tipo_obra: string
  modalidad: string
  costo: number | null
  estado_operativo: string
  fecha_inicio: string
  fin_programado: string
  fin_real: string | null
  sobreplazo: number | null
  retraso_significativo: number | null
  entidad: string
  modelo: string | null
  score: number | null
  nivel: Nivel | null
}

export const ESTADO_OP: Record<string, string> = {
  ACTIVA: 'Activa (en ejecución)',
  CONSUMADO: 'Retraso significativo ya consumado',
  FINALIZADA: 'Finalizada',
  DESACTUALIZADA: 'Sin registros recientes',
  OTRO: 'Otro',
}
const TIPOS = ['Transportes Y Comunicaciones', 'Educación/Cultura', 'Vivienda Construcción Y Saneamiento', 'Otras Infraestructuras', 'Agricultura', 'Salud', 'Energía Y Minas', 'Orden Público/Defensa Y Seguridad']
const MODALIDADES = ['Contrata', 'Administración directa', 'Por núcleo ejecutor', 'Obras por impuestos']

export default function Cartera() {
  const { departamento } = useAmbito()
  const [f, setF] = useState({ estado: 'ACTIVA', tipo_obra: '', modalidad: '', nivel: '', orden: 'riesgo', q: '' })
  const [buscar, setBuscar] = useState('')
  const [pagina, setPagina] = useState(1)
  const params = { ...f, q: buscar, departamento, pagina, tamanio: 25 }
  const r = useQuery({ queryKey: ['cartera', params], queryFn: () => api<{ total: number; items: Item[] }>(`/cartera${qs(params)}`) })
  const set = (k: string, v: string) => {
    setF({ ...f, [k]: v })
    setPagina(1)
  }
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-marca-900">Cartera nacional de obras (INFOBRAS)</h1>
        <p className="text-sm text-slate-600">
          Todas las modalidades (contrata, administración directa, núcleo ejecutor…) y sectores. Riesgo de terminar con <b>retraso significativo</b> (fin real posterior
          al fin programado original más 30% del plazo), estimado al inicio de la obra y actualizado mensualmente con la ejecución financiera del SIAF.
        </p>
      </div>
      <form
        className="tarjeta flex flex-wrap items-end gap-3 p-3"
        onSubmit={(e) => {
          e.preventDefault()
          setBuscar(f.q)
          setPagina(1)
        }}
      >
        <label className="min-w-60 flex-1 text-sm">
          <div className="etiqueta mb-1">Buscar (obra, entidad, CUI o código INFOBRAS)</div>
          <input className="entrada w-full" value={f.q} maxLength={120} onChange={(e) => setF({ ...f, q: e.target.value })} />
        </label>
        <label className="text-sm">
          <div className="etiqueta mb-1">Estado</div>
          <select className="entrada" value={f.estado} onChange={(e) => set('estado', e.target.value)}>
            {Object.entries(ESTADO_OP)
              .filter(([k]) => k !== 'OTRO')
              .map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            <option value="">Todos</option>
          </select>
        </label>
        <label className="text-sm">
          <div className="etiqueta mb-1">Tipo de obra</div>
          <select className="entrada max-w-56" value={f.tipo_obra} onChange={(e) => set('tipo_obra', e.target.value)}>
            <option value="">Todos</option>
            {TIPOS.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <div className="etiqueta mb-1">Modalidad</div>
          <select className="entrada" value={f.modalidad} onChange={(e) => set('modalidad', e.target.value)}>
            <option value="">Todas</option>
            {MODALIDADES.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <div className="etiqueta mb-1">Nivel</div>
          <select className="entrada" value={f.nivel} onChange={(e) => set('nivel', e.target.value)}>
            <option value="">Todos</option>
            <option>ALTO</option>
            <option>MEDIO</option>
            <option>BAJO</option>
          </select>
        </label>
        <label className="text-sm">
          <div className="etiqueta mb-1">Orden</div>
          <select className="entrada" value={f.orden} onChange={(e) => set('orden', e.target.value)}>
            <option value="riesgo">Mayor riesgo</option>
            <option value="monto">Mayor monto</option>
            <option value="reciente">Inicio más reciente</option>
          </select>
        </label>
        <button className="btn-primario">Buscar</button>
      </form>
      {r.isLoading ? (
        <Cargando />
      ) : r.error ? (
        <ErrorMsg error={r.error} />
      ) : (
        <div className="tarjeta p-3">
          <div className="overflow-x-auto">
            <table className="tabla w-full">
              <thead>
                <tr>
                  <th>Obra</th>
                  <th>Ubicación</th>
                  <th>Tipo / modalidad</th>
                  <th className="text-right">Costo</th>
                  <th>Plazo</th>
                  <th>Riesgo</th>
                  <th>Resultado observado</th>
                </tr>
              </thead>
              <tbody>
                {r.data!.items.map((o) => (
                  <tr key={o.codigo_infobras}>
                    <td className="max-w-md">
                      <Link to={`/cartera/${o.codigo_infobras}`} className="font-medium text-marca-700 hover:underline">
                        {o.nombre.slice(0, 150)}
                        {o.nombre.length > 150 ? '…' : ''}
                      </Link>
                      <div className="text-xs text-slate-500">
                        {o.entidad} · {ESTADO_OP[o.estado_operativo] ?? o.estado_operativo}
                      </div>
                    </td>
                    <td className="text-xs">
                      {o.provincia}
                      <br />
                      <span className="text-slate-500">{o.departamento}</span>
                    </td>
                    <td className="text-xs">
                      {o.tipo_obra}
                      <br />
                      <span className="text-slate-500">{o.modalidad}</span>
                    </td>
                    <td className="whitespace-nowrap text-right text-xs">{fmtMillones(o.costo)}</td>
                    <td className="whitespace-nowrap text-xs">
                      {fmtFecha(o.fecha_inicio)}
                      <br />
                      <span className="text-slate-500">fin prog. {fmtFecha(o.fin_programado)}</span>
                    </td>
                    <td className="whitespace-nowrap">
                      <NivelBadge nivel={o.nivel} score={o.score} />
                      <div className="text-[11px] text-slate-500">{o.modelo === 'seguimiento' ? 'seguimiento SIAF' : o.modelo ? 'al inicio' : ''}</div>
                    </td>
                    <td className="text-xs">
                      {o.retraso_significativo === null ? (
                        <span className="text-slate-500">aún no determinable</span>
                      ) : o.retraso_significativo ? (
                        <span className="font-medium text-alto">con retraso significativo{o.sobreplazo !== null ? ` (+${fmtPct(o.sobreplazo)} del plazo)` : ''}</span>
                      ) : (
                        <span className="text-bajo">sin retraso significativo</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Paginacion pagina={pagina} total={r.data!.total} tamanio={25} onChange={setPagina} />
        </div>
      )}
    </div>
  )
}
