import { useSearchParams } from 'react-router-dom'

// Estado de filtros sincronizado con la URL: permite compartir y volver a una vista filtrada.
export function useFiltrosUrl<T extends Record<string, string>>(defectos: T) {
  const [sp, setSp] = useSearchParams()
  const valores = Object.fromEntries(Object.keys(defectos).map((k) => [k, sp.get(k) ?? defectos[k]])) as T
  const pagina = Math.max(1, Number(sp.get('pagina') ?? 1) || 1)
  const set = (cambios: Partial<Record<keyof T | 'pagina', string | number | null>>) => {
    const n = new URLSearchParams(sp)
    for (const [k, v] of Object.entries(cambios)) {
      const def = k === 'pagina' ? '1' : defectos[k as keyof T]
      if (v === null || v === undefined || String(v) === def) n.delete(k)
      else n.set(k, String(v))
    }
    if (!('pagina' in cambios)) n.delete('pagina')
    setSp(n, { replace: true })
  }
  const limpiar = () => setSp(new URLSearchParams(), { replace: true })
  return { valores, pagina, set, limpiar, activos: Object.keys(defectos).filter((k) => valores[k] !== defectos[k]) }
}
