import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, fmtFecha, qs, type ObraResumen } from '../api'
import { Cargando, ErrorMsg, ESTADOS, NivelBadge, Paginacion, PROVINCIAS, SECTORES } from '../components/ui'

export default function Obras() {
  const [f, setF] = useState({ q: '', provincia: '', sector: '', estado: '', nivel: '', orden: 'riesgo' })
  const [pagina, setPagina] = useState(1)
  const [busqueda, setBusqueda] = useState('')
  const params = { ...f, q: busqueda, pagina, tamanio: 25 }
  const r = useQuery({ queryKey: ['obras', params], queryFn: () => api<{ total: number; items: ObraResumen[] }>(`/obras${qs(params)}`) })
  const set = (k: string, v: string) => {
    setF({ ...f, [k]: v })
    setPagina(1)
  }
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-marca-900">Obras</h1>
        <p className="text-sm text-slate-500">Contratos de obra con cuaderno de obra digital (OECE) ubicados en Arequipa, integrados con Invierte.pe, SIAF, INFOBRAS y SEACE.</p>
      </div>
      <form
        className="tarjeta flex flex-wrap items-end gap-3 p-3"
        onSubmit={(e) => {
          e.preventDefault()
          setBusqueda(f.q)
          setPagina(1)
        }}
      >
        <label className="min-w-64 flex-1 text-sm">
          <div className="etiqueta mb-1">Buscar (nombre, entidad o CUI)</div>
          <input className="entrada w-full" value={f.q} maxLength={120} onChange={(e) => setF({ ...f, q: e.target.value })} placeholder="p.ej. agua potable, 2345678" />
        </label>
        {(
          [
            ['provincia', 'Provincia', PROVINCIAS],
            ['sector', 'Sector', SECTORES],
          ] as const
        ).map(([k, l, ops]) => (
          <label key={k} className="text-sm">
            <div className="etiqueta mb-1">{l}</div>
            <select className="entrada" value={f[k]} onChange={(e) => set(k, e.target.value)}>
              <option value="">Todos</option>
              {ops.map((o) => (
                <option key={o}>{o}</option>
              ))}
            </select>
          </label>
        ))}
        <label className="text-sm">
          <div className="etiqueta mb-1">Estado</div>
          <select className="entrada" value={f.estado} onChange={(e) => set('estado', e.target.value)}>
            <option value="">Todos</option>
            {Object.entries(ESTADOS).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
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
            <option value="reciente">Actividad reciente</option>
            <option value="nombre">Nombre</option>
          </select>
        </label>
        <button className="btn-primario" type="submit">
          Buscar
        </button>
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
                  <th>Provincia</th>
                  <th>Sector</th>
                  <th>Estado</th>
                  <th>Último riesgo</th>
                  <th>Atraso normativo</th>
                </tr>
              </thead>
              <tbody>
                {r.data!.items.map((o) => (
                  <tr key={o.cuaderno_id}>
                    <td className="max-w-lg">
                      <Link to={`/obras/${o.cuaderno_id}`} className="font-medium text-marca-700 hover:underline">
                        {o.denominacion.slice(0, 170)}
                        {o.denominacion.length > 170 ? '…' : ''}
                      </Link>
                      <div className="text-xs text-slate-500">
                        {o.entidad} {o.cui ? `· CUI ${o.cui}` : ''} · {o.n_asientos ?? 0} asientos
                      </div>
                    </td>
                    <td className="text-xs">
                      {o.provincia}
                      <br />
                      <span className="text-slate-500">{o.distrito}</span>
                    </td>
                    <td className="text-xs">{o.sector}</td>
                    <td className="text-xs">{ESTADOS[o.estado_observado] ?? o.estado_observado}</td>
                    <td className="whitespace-nowrap">
                      <NivelBadge nivel={o.nivel} score={o.score} />
                      <div className="text-xs text-slate-500">{o.fecha_corte ? `${o.tipo_prediccion === 'vigente' ? 'vigente' : 'histórico'} · ${fmtFecha(o.fecha_corte)}` : ''}</div>
                    </td>
                    <td className="whitespace-nowrap text-xs">{o.fecha_atraso ? <span className="font-medium text-alto">{fmtFecha(o.fecha_atraso)}</span> : '—'}</td>
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
