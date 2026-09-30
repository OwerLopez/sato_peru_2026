// Copia estatica de solo lectura (GitHub Pages). La interfaz lee respuestas reales de la API guardadas como archivos
// JSON por scripts/exportar_estatico.py a partir de la base cargada; no hay servidor ni base de datos detras.
// La clave de cada archivo es un hash de la ruta con los parametros ordenados (el exportador calcula el mismo hash).
export const ESTATICO = import.meta.env.VITE_ESTATICO === '1'
export const BASE = import.meta.env.BASE_URL

function fnv1a(s: string, h: number): string {
  for (const b of new TextEncoder().encode(s)) h = Math.imul(h ^ b, 0x01000193) >>> 0
  return h.toString(16).padStart(8, '0')
}

export function claveDatos(ruta: string): string {
  const [p, q = ''] = ruta.split('?')
  const pares = [...new URLSearchParams(q).entries()].sort(([a, x], [b, y]) => (a === b ? (x < y ? -1 : x > y ? 1 : 0) : a < b ? -1 : 1))
  const norm = p + (pares.length ? '?' + pares.map(([k, v]) => `${k}=${v}`).join('&') : '')
  return fnv1a(norm, 0x811c9dc5) + fnv1a(norm, 0x050c5d1f)
}

export const urlPdf = (cuadernoId: string) => (ESTATICO ? `${BASE}datos/pdf/${cuadernoId}.pdf` : `/api/v1/obras/${cuadernoId}/informe-pdf`)
