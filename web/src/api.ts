// Cliente de la API REST de SATO-AQP (mismo origen: nginx hace proxy de /api).
export const API = '/api/v1'

let token: string | null = sessionStorage.getItem('sato_token')
export const setToken = (t: string | null) => {
  token = t
  if (t) sessionStorage.setItem('sato_token', t)
  else sessionStorage.removeItem('sato_token')
}
export const getToken = () => token

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json', ...(init.headers as Record<string, string>) }
  if (token) headers.Authorization = `Bearer ${token}`
  const r = await fetch(`${API}${path}`, { ...init, headers })
  if (!r.ok) {
    let msg = r.statusText
    try {
      const j = await r.json()
      msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
    } catch {
      /* respuesta sin JSON */
    }
    throw new ApiError(r.status, msg)
  }
  return r.json() as Promise<T>
}

export const qs = (o: Record<string, unknown>) => {
  const p = new URLSearchParams()
  Object.entries(o).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') p.set(k, String(v))
  })
  const s = p.toString()
  return s ? `?${s}` : ''
}

export type Nivel = 'ALTO' | 'MEDIO' | 'BAJO'

export interface ObraResumen {
  cuaderno_id: string
  denominacion: string
  provincia: string | null
  distrito: string | null
  sector: string | null
  cui: string | null
  estado_observado: string
  entidad: string | null
  primer_asiento: string | null
  ultimo_asiento: string | null
  n_asientos: number | null
  fecha_atraso: string | null
  prediccion_id: number | null
  fecha_corte: string | null
  score: number | null
  nivel: Nivel | null
  alerta: boolean | null
  percentil: number | null
  tipo_prediccion: 'backtest' | 'vigente' | null
}

export interface Factor {
  rango?: number
  feature?: string
  grupo: string
  valor?: number | null
  shap: number
  descripcion: string
}

export interface Evidencia {
  feature: string
  fuente: string
  fecha: string | null
  referencia: string | null
  extracto: string | null
  asiento_id: number | null
  nro_asiento: number | null
  tipo: string | null
  rol: string | null
  titulo: string | null
  archivo_fuente: string | null
}

export const fmtFecha = (s?: string | null) => (s ? new Date(s.length === 10 ? s + 'T12:00:00' : s).toLocaleDateString('es-PE', { year: 'numeric', month: 'short', day: 'numeric' }) : '—')
export const fmtMes = (s?: string | null) => (s ? new Date(s.length === 10 ? s + 'T12:00:00' : s).toLocaleDateString('es-PE', { year: 'numeric', month: 'short' }) : '—')
export const fmtPct = (x?: number | null, d = 0) => (x === null || x === undefined ? '—' : `${(100 * x).toFixed(d)}%`)
export const fmtNum = (x?: number | null, d = 0) => (x === null || x === undefined ? '—' : x.toLocaleString('es-PE', { maximumFractionDigits: d, minimumFractionDigits: d }))
export const fmtSoles = (x?: number | null) => (x === null || x === undefined ? '—' : `S/ ${x.toLocaleString('es-PE', { maximumFractionDigits: 0 })}`)
export const ROL: Record<string, string> = { SOEC_RESI: 'Residente', SOEC_SPV: 'Supervisor', SOEC_INSP: 'Inspector', SOEC_JEEXPTE: 'Jefe de expediente', SOEC_LIDER: 'Líder' }
