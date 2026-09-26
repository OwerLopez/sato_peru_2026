import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, fmtMillones, fmtNum, fmtPct } from '../api'
import { useAmbito } from '../ambito'
import { Cargando, ErrorMsg, Seccion } from '../components/ui'

interface Fila {
  clave: string
  obras: number
  tasa_retraso_historica: number | null
  obras_con_resultado: number
  activas: number
  activas_alto: number
  monto_activo: number | null
  cuaderno_evaluadas: number
  cuaderno_alto: number
}

export default function Comparador() {
  const [por, setPor] = useState<'departamento' | 'sector'>('departamento')
  const { departamento } = useAmbito()
  const q = useQuery({ queryKey: ['comparador', por], queryFn: () => api<{ cartera: Fila[] }>(`/comparador?por=${por}`) })
  if (q.isLoading) return <Cargando />
  if (q.error) return <ErrorMsg error={q.error} />
  const filas = q.data!.cartera.filter((f) => f.obras_con_resultado >= 30)
  const graf = [...filas]
    .sort((a, b) => (b.tasa_retraso_historica ?? 0) - (a.tasa_retraso_historica ?? 0))
    .map((f) => ({ clave: f.clave, 'Retraso significativo histórico (%)': Math.round(100 * (f.tasa_retraso_historica ?? 0)), 'Activas en nivel alto (%)': f.activas ? Math.round((100 * f.activas_alto) / f.activas) : 0 }))
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-marca-900">Comparador territorial y sectorial</h1>
          <p className="text-sm text-slate-600">
            Tasa histórica observada de retraso significativo (obras con resultado determinable en INFOBRAS) frente al riesgo vigente de las obras activas. Solo se
            muestran grupos con al menos 30 obras con resultado.
          </p>
        </div>
        <div className="flex gap-2">
          <button className={por === 'departamento' ? 'btn-primario' : 'btn'} onClick={() => setPor('departamento')}>
            Por departamento
          </button>
          <button className={por === 'sector' ? 'btn-primario' : 'btn'} onClick={() => setPor('sector')}>
            Por tipo de obra
          </button>
        </div>
      </div>
      <Seccion titulo={por === 'departamento' ? 'Departamentos' : 'Tipos de obra'} subtitulo="Ordenado por tasa histórica de retraso significativo.">
        <div style={{ height: Math.max(320, graf.length * 22) }}>
          <ResponsiveContainer>
            <BarChart data={graf} layout="vertical" margin={{ left: 90 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" unit="%" domain={[0, 100]} tick={{ fontSize: 11 }} />
              <YAxis dataKey="clave" type="category" tick={{ fontSize: 10 }} width={170} />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar isAnimationActive={false} dataKey="Retraso significativo histórico (%)" fill="#1b5f8c" />
              <Bar isAnimationActive={false} dataKey="Activas en nivel alto (%)" fill="#b91c1c" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Seccion>
      <Seccion titulo="Tabla comparativa">
        <div className="overflow-x-auto">
          <table className="tabla w-full">
            <thead>
              <tr>
                <th>{por === 'departamento' ? 'Departamento' : 'Tipo de obra'}</th>
                <th className="text-right">Obras</th>
                <th className="text-right">Con resultado</th>
                <th className="text-right">Retraso significativo histórico</th>
                <th className="text-right">Activas</th>
                <th className="text-right">Activas nivel alto</th>
                <th className="text-right">Monto activo</th>
                {por === 'departamento' && <th className="text-right">Cuaderno digital evaluadas / alto</th>}
              </tr>
            </thead>
            <tbody>
              {filas.map((f) => (
                <tr key={f.clave} className={f.clave === departamento ? 'bg-amber-50' : ''}>
                  <td>{f.clave}</td>
                  <td className="text-right">{fmtNum(f.obras)}</td>
                  <td className="text-right">{fmtNum(f.obras_con_resultado)}</td>
                  <td className="text-right">{fmtPct(f.tasa_retraso_historica)}</td>
                  <td className="text-right">{fmtNum(f.activas)}</td>
                  <td className="text-right">{fmtNum(f.activas_alto)}</td>
                  <td className="text-right">{fmtMillones(f.monto_activo)}</td>
                  {por === 'departamento' && (
                    <td className="text-right">
                      {fmtNum(f.cuaderno_evaluadas)} / {fmtNum(f.cuaderno_alto)}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Seccion>
    </div>
  )
}
