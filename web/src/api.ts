// Cliente de la API REST de SATO (mismo origen: nginx hace proxy de /api).
import { useQuery } from '@tanstack/react-query'
import { BASE, claveDatos, ESTATICO } from './estatico'

export const API = '/api/v1'

// La sesión vive en sessionStorage (se borra al cerrar la pestaña) y se descarta al vencer el token.
// Se envía como cabecera Authorization (no como cookie), por lo que no aplica la falsificación de solicitudes (CSRF).
let token: string | null = null
let expira = 0
try {
  token = sessionStorage.getItem('sato_token')
  expira = Number(sessionStorage.getItem('sato_token_exp') ?? 0)
} catch {
  /* almacenamiento no disponible */
}
export const SESION_EXPIRADA = 'sato:sesion-expirada'
export const setToken = (t: string | null, minutos = 0) => {
  token = t
  expira = t && minutos > 0 ? Date.now() + minutos * 60_000 : 0
  try {
    if (t) {
      sessionStorage.setItem('sato_token', t)
      sessionStorage.setItem('sato_token_exp', String(expira))
    } else {
      sessionStorage.removeItem('sato_token')
      sessionStorage.removeItem('sato_token_exp')
    }
  } catch {
    /* almacenamiento no disponible */
  }
}
export const getToken = () => {
  if (token && expira && Date.now() > expira) setToken(null)
  return token
}

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

async function apiEstatica<T>(path: string, init: RequestInit): Promise<T> {
  if ((init.method ?? 'GET').toUpperCase() !== 'GET')
    throw new ApiError(0, 'Esta es una copia pública de solo lectura: el ingreso de analistas, las suscripciones y las revisiones están disponibles en la versión completa del sistema.')
  let r: Response
  try {
    r = await fetch(`${BASE}datos/${claveDatos(path)}.json`)
  } catch {
    throw new ApiError(0, 'No hay conexión. Verifique su red e intente de nuevo.')
  }
  if (!r.ok)
    throw new ApiError(404, 'Esta consulta no está incluida en la copia pública de demostración. La versión completa del sistema responde cualquier combinación de filtros y búsquedas.')
  return (await r.json()) as T
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (ESTATICO) return apiEstatica<T>(path, init)
  const headers: Record<string, string> = { 'Content-Type': 'application/json', ...(init.headers as Record<string, string>) }
  const t = getToken()
  if (t) headers.Authorization = `Bearer ${t}`
  let r: Response
  try {
    r = await fetch(`${API}${path}`, { ...init, headers })
  } catch {
    throw new ApiError(0, 'No hay conexión con el servidor. Verifique su red e intente de nuevo.')
  }
  if (r.status === 401 && t) {
    // token vencido o revocado: se cierra la sesión en toda la interfaz
    setToken(null)
    window.dispatchEvent(new Event(SESION_EXPIRADA))
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

export type EstadoGeneral = 'OPERATIVO' | 'CON_AVISOS' | 'DEGRADADO'
export interface Desempeno {
  T: string
  n: number
  eventos: number
  pr_auc: number
  recall_alerta: number
}
export interface EstadoSistema {
  estado: EstadoGeneral
  motivos: { nivel: 'INFO' | 'AVISO' | 'CRITICO'; componente: string; texto: string }[]
  verificado_en: string
  base_datos: { ok: boolean; latencia_ms: number }
  datos: { fecha_corte: string | null; dias_desde_corte: number | null; frescura: { fuente: string; ultimo_dato: string }[] | null }
  carga: { ultima: { inicio: string; fin: string | null; estado: string } | null; ultima_ok: string | null }
  calidad: Partial<Record<'OK' | 'AVISO' | 'INFO' | 'CRITICO', number>> | null
  modelo: { version: string; entrenado_hasta: string; horizonte_dias: number; variables_con_deriva: number; anomalia_nivel_alto: boolean | null; desempeno_realizado: Desempeno[] } | null
  sincronizacion: { inicio: string; fin: string | null; estado: string } | null
  worker: { ultimo_latido: string; detalle: Record<string, unknown> } | null
}
export interface Monitoreo {
  alertas: string[]
  psi_detalle?: { variable: string; etiqueta: string; psi: number }[]
  desempeno_realizado: Desempeno[]
  anomalia_nivel_alto?: {
    evaluable: boolean
    motivo?: string
    corte?: string
    tasa?: number
    mediana?: number
    z?: number
    umbral_z?: number
    anomala?: boolean
    cortes_historicos?: number
    serie?: { T: string; tipo: string; tasa: number }[]
  }
  cobertura_mensual: { mes: string; asientos: number; cuadernos_activos: number; var_vs_6m: number | null }[]
  tipos_sin_armonizar: Record<string, number>
}
export interface Carga {
  id: number
  inicio: string
  fin: string | null
  estado: 'EN_CURSO' | 'OK' | 'RECHAZADA' | 'ERROR'
  conteos: Record<string, number> | null
  conciliacion: Record<string, { origen: number; cargadas: number; descartadas: number; motivo: string }> | null
  validacion: { entradas?: string[]; criticos?: string[]; caidas?: string[]; forzada?: boolean; max_caida?: number } | null
  mensaje: string | null
}
export const useEstado = () => useQuery({ queryKey: ['estado'], queryFn: () => api<EstadoSistema>('/sistema/estado'), staleTime: 60_000, refetchInterval: 5 * 60_000 })

/** Solo enlaces http(s): un valor de la fuente con otro esquema (javascript:, data:) no se convierte en enlace. */
export const urlSegura = (u?: string | null) => {
  if (!u) return null
  try {
    const x = new URL(u)
    return x.protocol === 'https:' || x.protocol === 'http:' ? x.href : null
  } catch {
    return null
  }
}

export const useCalibracion = () => useQuery({ queryKey: ['calibracion'], queryFn: () => api<Calibracion>('/modelo/calibracion'), staleTime: Infinity })
export const useFiltros = () => useQuery({ queryKey: ['filtros'], queryFn: () => api<Filtros>('/filtros'), staleTime: Infinity })

const fecha = (s: string) => new Date(s.length === 10 ? s + 'T12:00:00' : s)
export const fmtFecha = (s?: string | null) => (s ? fecha(s).toLocaleDateString('es-PE', { year: 'numeric', month: 'short', day: 'numeric' }) : '—')
export const fmtMes = (s?: string | null) => (s ? fecha(s).toLocaleDateString('es-PE', { year: 'numeric', month: 'short' }) : '—')
// espacio no separable (U+00A0) entre número y unidad: la cifra nunca se parte en dos líneas
const NBSP = '\u00a0'
export const fmtPct = (x?: number | null, d = 0) => (x === null || x === undefined || Number.isNaN(x) ? '—' : `${(100 * x).toLocaleString('es-PE', { maximumFractionDigits: d, minimumFractionDigits: d })}${NBSP}%`)
export const fmtNum = (x?: number | null, d = 0) => (x === null || x === undefined || Number.isNaN(x) ? '—' : x.toLocaleString('es-PE', { maximumFractionDigits: d, minimumFractionDigits: d }))
export const fmtDec = (x?: number | null, d = 2) => (x === null || x === undefined || Number.isNaN(x) ? '—' : x.toLocaleString('es-PE', { minimumFractionDigits: d, maximumFractionDigits: d }))
export const fmtSoles = (x?: number | null) => (x === null || x === undefined ? '—' : `S/${NBSP}${x.toLocaleString('es-PE', { maximumFractionDigits: 0 })}`)
export const fmtMillones = (x?: number | null) =>
  x === null || x === undefined
    ? '—'
    : x >= 1e9
      ? `S/${NBSP}${(x / 1e9).toLocaleString('es-PE', { maximumFractionDigits: 2 })} mil${NBSP}millones`
      : x >= 1e6
        ? `S/${NBSP}${(x / 1e6).toLocaleString('es-PE', { maximumFractionDigits: 1 })} millones`
        : fmtSoles(x)
/** Monto en dos partes (cifra y unidad) para mostrarlo grande sin que se parta en dos líneas. */
export const montoPartes = (x?: number | null): { valor: string; unidad: string } =>
  x === null || x === undefined
    ? { valor: '—', unidad: '' }
    : x >= 1e9
      ? { valor: (x / 1e9).toLocaleString('es-PE', { maximumFractionDigits: 1 }), unidad: 'mil millones de soles' }
      : x >= 1e6
        ? { valor: (x / 1e6).toLocaleString('es-PE', { maximumFractionDigits: 1 }), unidad: 'millones de soles' }
        : { valor: x.toLocaleString('es-PE', { maximumFractionDigits: 0 }), unidad: 'soles' }
const MENORES = new Set(['de', 'del', 'la', 'las', 'los', 'el', 'y', 'e', 'en', 'a', 'al', 'con', 'para', 'por', 'o', 'u', 'sin', 'sobre'])
export const titulo = (s?: string | null) =>
  s
    ? s
        .toLocaleLowerCase('es-PE')
        .replace(/(^|[\s(/-])(\p{L}+)/gu, (_, a: string, w: string) => a + (a && MENORES.has(w) ? w : w.charAt(0).toLocaleUpperCase('es-PE') + w.slice(1)))
    : '—'

// Siglas y abreviaturas que se conservan en mayúsculas al mostrar nombres publicados íntegramente en mayúsculas
const SIGLAS = new Set(['CUI', 'SNIP', 'IE', 'IEI', 'IEP', 'PRONEI', 'PSI', 'EPS', 'SAC', 'SRL', 'EIRL', 'SA', 'MDL', 'GM', 'GR', 'KV', 'MT', 'BT', 'SET', 'PTAR', 'PTAP',
  'MEF', 'MTC', 'MINSA', 'MINEDU', 'MVCS', 'PNSU', 'PNSR', 'OECE', 'SEACE', 'SUNAT', 'SEDAPAL', 'ESSALUD', 'IOARR', 'PIP', 'UGEL', 'UNSA', 'EMAPA', 'SEDAPAR', 'II', 'III', 'IV',
  'VI', 'VII', 'VIII', 'IX', 'XI', 'XII', 'AAHH', 'CP', 'CC', 'CCPP', 'RD', 'RM', 'DS', 'N', 'SN', 'S/N'])
/** Nombre legible para textos publicados en mayúsculas: mayúscula inicial por palabra, conectores en minúscula,
 *  siglas, códigos y abreviaturas intactos. El nombre original se conserva en la ficha. */
export const nombreObra = (s?: string | null) => {
  if (!s) return '—'
  const letras = s.replace(/[^\p{L}]/gu, '')
  const minusculas = letras.replace(/[^\p{Ll}]/gu, '').length
  if (letras && minusculas / letras.length > 0.2) return s // ya viene en mayúsculas y minúsculas: se respeta
  const palabra = (w: string, inicio: boolean): string => {
    const base = w.replace(/[.°º]/g, '')
    // siglas conocidas, códigos con dígitos y abreviaturas (I.E., AA., HH., AV.) se conservan
    if (/\d/.test(w) || SIGLAS.has(base) || /^(\p{L}\.){2,}/u.test(w) || (w.endsWith('.') && base.length <= 3)) return w
    const l = w.toLocaleLowerCase('es-PE')
    return !inicio && MENORES.has(l) ? l : l.charAt(0).toLocaleUpperCase('es-PE') + l.slice(1)
  }
  return s.replace(/[\p{L}\p{N}./°º]+/gu, (w, pos: number) => {
    // inicio de frase: comienzo del texto o después de dos puntos, comillas o paréntesis
    const inicio = pos === 0 || /[:"«(¿]\s*$/.test(s.slice(Math.max(0, pos - 3), pos))
    return w.includes('/') && !/\d/.test(w) ? w.split('/').map((x) => (x ? palabra(x, inicio) : x)).join('/') : palabra(w, inicio)
  })
}

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
