import { useQuery } from '@tanstack/react-query'
import { ArrowDown, ArrowUp } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, fmtMillones, fmtNum, fmtPct, titulo } from '../api'
import { useAmbito } from '../ambito'
import { BarraProporcion, Cargando, EncabezadoPagina, ErrorMsg, InfoTip, Seccion, Segmentado } from '../components/ui'
import { COLOR_NIVEL, COLORES, SERIE } from '../lib/colores'

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
type Col = 'clave' | 'obras' | 'tasa_retraso_historica' | 'activas' | 'pct_alto' | 'monto_activo'
type Orden = { c: Col; asc: boolean }

function Th({ c, children, right, orden, setOrden }: { c: Col; children: ReactNode; right?: boolean; orden: Orden; setOrden: (o: Orden) => void }) {
  return (
    <th className={right ? 'text-right' : ''} aria-sort={orden.c === c ? (orden.asc ? 'ascending' : 'descending') : 'none'}>
      <button className={`inline-flex items-center gap-1 uppercase ${right ? 'flex-row-reverse' : ''}`} onClick={() => setOrden({ c, asc: orden.c === c ? !orden.asc : c === 'clave' })}>
        {children}
        {orden.c === c && (orden.asc ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" />)}
      </button>
    </th>
  )
}

export default function Comparador() {
  const [por, setPor] = useState<'departamento' | 'sector'>('departamento')
  const [orden, setOrden] = useState<Orden>({ c: 'tasa_retraso_historica', asc: false })
  const { departamento } = useAmbito()
  const q = useQuery({ queryKey: ['comparador', por], queryFn: () => api<{ cartera: Fila[] }>(`/comparador?por=${por}`) })
  const filas = (q.data?.cartera ?? [])
    .filter((f) => f.obras_con_resultado >= 30)
    .map((f) => ({ ...f, pct_alto: f.activas ? f.activas_alto / f.activas : 0 }))
  const val = (f: (typeof filas)[number], c: Col) => (c === 'clave' ? f.clave : (f[c] ?? -1))
  const ordenadas = [...filas].sort((a, b) => {
    const x = val(a, orden.c)
    const y = val(b, orden.c)
    const r = typeof x === 'string' ? x.localeCompare(String(y)) : Number(x) - Number(y)
    return orden.asc ? r : -r
  })
  const graf = [...filas]
    .sort((a, b) => (b.tasa_retraso_historica ?? 0) - (a.tasa_retraso_historica ?? 0))
    .map((f) => ({ clave: por === 'departamento' ? titulo(f.clave) : f.clave, historica: Math.round(100 * (f.tasa_retraso_historica ?? 0)), alto: Math.round(100 * f.pct_alto) }))
  const maxTasa = Math.max(...filas.map((f) => f.tasa_retraso_historica ?? 0), 0.01)
  return (
    <div className="space-y-5">
      <EncabezadoPagina
        titulo="Comparador territorial y sectorial"
        descripcion="Compare dónde se concentran los retrasos: la tasa histórica observada en obras ya terminadas frente al riesgo estimado de las obras que hoy están en ejecución (cartera INFOBRAS)."
        acciones={
          <Segmentado
            etiqueta="Agrupar por"
            valor={por}
            onChange={setPor}
            opciones={[
              { v: 'departamento', l: 'Por departamento' },
              { v: 'sector', l: 'Por tipo de obra' },
            ]}
          />
        }
      />
      {q.isLoading ? (
        <Cargando filas={8} />
      ) : q.error ? (
        <ErrorMsg error={q.error} reintentar={() => q.refetch()} />
      ) : (
        <>
          <Seccion
            titulo={por === 'departamento' ? 'Retraso por departamento' : 'Retraso por tipo de obra'}
            ayuda="retraso_significativo"
            subtitulo="Ordenado por tasa histórica. Solo grupos con al menos 30 obras con resultado conocido."
          >
            <div style={{ height: Math.max(300, graf.length * 26 + 50) }}>
              <ResponsiveContainer>
                <BarChart data={graf} layout="vertical" margin={{ left: 4, right: 16 }} barGap={1}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke={COLORES.rejilla} />
                  <XAxis type="number" unit="%" domain={[0, 100]} tick={{ fontSize: 11 }} />
                  <YAxis dataKey="clave" type="category" tick={{ fontSize: 11 }} width={por === 'departamento' ? 110 : 210} interval={0} />
                  <Tooltip formatter={(v) => `${v} %`} cursor={{ fill: '#f1f5f9' }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar isAnimationActive={false} dataKey="historica" name="Obras terminadas con retraso significativo" fill={SERIE[0]} radius={[0, 3, 3, 0]} />
                  <Bar isAnimationActive={false} dataKey="alto" name="Obras en ejecución con riesgo alto" fill={COLOR_NIVEL.ALTO} radius={[0, 3, 3, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Seccion>
          <Seccion titulo="Tabla comparativa" subtitulo="Haga clic en un encabezado para ordenar." sinRelleno>
            <div className="max-h-[560px] overflow-auto">
              <table className="tabla min-w-[820px]">
                <thead>
                  <tr>
                    <Th c="clave" orden={orden} setOrden={setOrden}>{por === 'departamento' ? 'Departamento' : 'Tipo de obra'}</Th>
                    <Th c="obras" right orden={orden} setOrden={setOrden}>
                      Obras registradas
                    </Th>
                    <Th c="tasa_retraso_historica" orden={orden} setOrden={setOrden}>Retraso histórico</Th>
                    <Th c="activas" right orden={orden} setOrden={setOrden}>
                      En ejecución
                    </Th>
                    <Th c="pct_alto" right orden={orden} setOrden={setOrden}>
                      Con riesgo alto
                    </Th>
                    <Th c="monto_activo" right orden={orden} setOrden={setOrden}>
                      Inversión en ejecución
                    </Th>
                  </tr>
                </thead>
                <tbody>
                  {ordenadas.map((f) => (
                    <tr key={f.clave} className={f.clave === departamento ? 'bg-marca-50' : ''}>
                      <td className="font-medium text-slate-800">{por === 'departamento' ? titulo(f.clave) : f.clave}</td>
                      <td className="num text-right">{fmtNum(f.obras)}</td>
                      <td className="min-w-44">
                        <div className="flex items-center gap-2">
                          <span className="num w-12 shrink-0 text-right">{fmtPct(f.tasa_retraso_historica)}</span>
                          <BarraProporcion valor={f.tasa_retraso_historica ?? 0} max={maxTasa} />
                        </div>
                        <div className="text-xs text-slate-500">de {fmtNum(f.obras_con_resultado)} con resultado</div>
                      </td>
                      <td className="num text-right">{fmtNum(f.activas)}</td>
                      <td className="num text-right">
                        {fmtNum(f.activas_alto)} <span className="text-xs text-slate-500">({fmtPct(f.pct_alto)})</span>
                      </td>
                      <td className="num text-right whitespace-nowrap">{fmtMillones(f.monto_activo)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Seccion>
          <p className="flex items-start gap-1 text-xs text-slate-500">
            <InfoTip termino="nivel" />
            El riesgo alto de la cartera corresponde al 20 % de mayor riesgo del periodo de referencia; por eso su proporción en cada grupo se compara entre grupos y no con el 100 %.
          </p>
        </>
      )}
    </div>
  )
}
