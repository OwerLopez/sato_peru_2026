// Cliente de la API REST de SATO (mismo origen: nginx hace proxy de /api).
import { useQuery } from '@tanstack/react-query'

export const API = '/api/v1'

let token: string | null = null
try {
  token = sessionStorage.getItem('sato_token')
} catch {
  /* almacenamiento no disponible */
}
export const setToken = (t: string | null) => {
  token = t
  try {
    if (t) sessionStorage.setItem('sato_token', t)
    else sessionStorage.removeItem('sato_token')
  } catch {
    /* almacenamiento no disponible */
  }
}
export const getToken = () => token

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

const MENSAJES: Record<number, string> = {
  401: 'Debe ingresar para realizar esta acción.',
  403: 'Su usuario no tiene permiso para esta acción.',
  404: 'No se encontró la información solicitada.',
  422: 'Los datos enviados no son válidos.',
  429: 'Demasiadas solicitudes seguidas. Espere un momento e intente de nuevo.',
  500: 'Ocurrió un error en el servidor. Intente nuevamente.',
  503: 'El servicio no está disponible en este momento.',
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json', ...(init.headers as Record<string, string>) }
  if (token) headers.Authorization = `Bearer ${token}`
  let r: Response
  try {
    r = await fetch(`${API}${path}`, { ...init, headers })
  } catch {
    throw new ApiError(0, 'No hay conexión con el servidor. Verifique su red e intente de nuevo.')
  }
  if (!r.ok) {
    let detalle: string | null = null
    try {
      const j = await r.json()
      detalle = typeof j.detail === 'string' ? j.detail : null
    } catch {
      /* respuesta sin JSON */
    }
    throw new ApiError(r.status, MENSAJES[r.status] ?? detalle ?? r.statusText)
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
  departamento: string | null
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

export interface Explicacion {
  prediccion: { id: number; fecha_corte: string; score: number; nivel: Nivel; tipo: string; horizonte_dias: number; umbral_alerta: number; modelo_version: string; y_observado: number | null; percentil: number | null }
  factores: Factor[]
  evidencia: Evidencia[]
}

export interface Calibracion {
  alerta_60d: {
    n: number
    tasa_base: number
    desde: string
    hasta: string
    niveles: { nivel: Nivel; n: number; probabilidad_media: number; tasa_observada: number; eventos: number }[]
    deciles: { decil: number; n: number; probabilidad_media: number; tasa_observada: number }[]
  }
  cartera: Record<'inicio' | 'seguimiento', { tasa_base: number; desde: string; niveles: { nivel: Nivel; filas: number; tasa_retraso_observada: number }[] }>
}

export interface Filtros {
  sectores: string[]
  tipos_obra: string[]
  modalidades: string[]
}

export const useCalibracion = () => useQuery({ queryKey: ['calibracion'], queryFn: () => api<Calibracion>('/modelo/calibracion'), staleTime: Infinity })
export const useFiltros = () => useQuery({ queryKey: ['filtros'], queryFn: () => api<Filtros>('/filtros'), staleTime: Infinity })

const fecha = (s: string) => new Date(s.length === 10 ? s + 'T12:00:00' : s)
export const fmtFecha = (s?: string | null) => (s ? fecha(s).toLocaleDateString('es-PE', { year: 'numeric', month: 'short', day: 'numeric' }) : '—')
export const fmtMes = (s?: string | null) => (s ? fecha(s).toLocaleDateString('es-PE', { year: 'numeric', month: 'short' }) : '—')
export const fmtPct = (x?: number | null, d = 0) => (x === null || x === undefined || Number.isNaN(x) ? '—' : `${(100 * x).toLocaleString('es-PE', { maximumFractionDigits: d, minimumFractionDigits: d })} %`)
export const fmtNum = (x?: number | null, d = 0) => (x === null || x === undefined || Number.isNaN(x) ? '—' : x.toLocaleString('es-PE', { maximumFractionDigits: d, minimumFractionDigits: d }))
export const fmtDec = (x?: number | null, d = 2) => (x === null || x === undefined || Number.isNaN(x) ? '—' : x.toLocaleString('es-PE', { minimumFractionDigits: d, maximumFractionDigits: d }))
export const fmtSoles = (x?: number | null) => (x === null || x === undefined ? '—' : `S/ ${x.toLocaleString('es-PE', { maximumFractionDigits: 0 })}`)
export const fmtMillones = (x?: number | null) =>
  x === null || x === undefined
    ? '—'
    : x >= 1e9
      ? `S/ ${(x / 1e9).toLocaleString('es-PE', { maximumFractionDigits: 2 })} mil millones`
      : x >= 1e6
        ? `S/ ${(x / 1e6).toLocaleString('es-PE', { maximumFractionDigits: 1 })} millones`
        : fmtSoles(x)
const MENORES = new Set(['de', 'del', 'la', 'las', 'los', 'el', 'y', 'e', 'en'])
export const titulo = (s?: string | null) =>
  s
    ? s
        .toLocaleLowerCase('es-PE')
        .replace(/(^|[\s(/-])(\p{L}+)/gu, (_, a: string, w: string) => a + (a && MENORES.has(w) ? w : w.charAt(0).toLocaleUpperCase('es-PE') + w.slice(1)))
    : '—'

export const ROL: Record<string, string> = { SOEC_RESI: 'Residente', SOEC_SPV: 'Supervisor', SOEC_INSP: 'Inspector', SOEC_JEEXPTE: 'Jefe de expediente', SOEC_LIDER: 'Líder' }
export const ESTADOS: Record<string, string> = { EN_EJECUCION: 'En ejecución', CULMINADA: 'Culminada', RESUELTA: 'Contrato resuelto', INACTIVA: 'Sin registros recientes' }
export const ESTADO_OP: Record<string, string> = {
  ACTIVA: 'En ejecución',
  CONSUMADO: 'Retraso ya consumado',
  FINALIZADA: 'Finalizada',
  DESACTUALIZADA: 'Sin registros recientes',
  OTRO: 'Otro estado',
}
export const SECTOR: Record<string, string> = {
  SANEAMIENTO: 'Saneamiento',
  TRANSPORTE: 'Transporte',
  EDUCACION: 'Educación',
  SALUD: 'Salud',
  AGROPECUARIA: 'Agropecuaria',
  OTROS: 'Otros sectores',
  SIN_CUI: 'Sin inversión enlazada',
}
