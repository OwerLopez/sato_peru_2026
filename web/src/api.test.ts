// Pruebas unitarias del cliente de la API y de los formatos que ve el usuario (npm test).
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, fmtMillones, fmtNum, fmtPct, getToken, qs, SESION_EXPIRADA, setToken, titulo, urlSegura } from './api'
import { GLOSARIO } from './glosario'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  setToken(null)
})

describe('formatos es-PE', () => {
  it('porcentajes con espacio y decimales fijos', () => {
    expect(fmtPct(0.176, 1)).toBe('17.6 %')
    expect(fmtPct(0.2)).toBe('20 %')
    expect(fmtPct(null)).toBe('—')
    expect(fmtPct(Number.NaN)).toBe('—')
  })
  it('miles y montos', () => {
    expect(fmtNum(96986)).toBe('96,986')
    expect(fmtMillones(2.5e9)).toBe('S/ 2.5 mil millones')
    expect(fmtMillones(3_400_000)).toBe('S/ 3.4 millones')
    expect(fmtMillones(undefined)).toBe('—')
  })
  it('nombres propios sin mayúsculas en las partículas', () => {
    expect(titulo('MADRE DE DIOS')).toBe('Madre de Dios')
    expect(titulo('construccion del puente y la via')).toBe('Construccion del Puente y la Via')
    expect(titulo(null)).toBe('—')
  })
  it('cadena de consulta sin valores vacíos', () => {
    expect(qs({ a: 1, b: null, c: '', d: undefined, e: 'x y' })).toBe('?a=1&e=x+y')
    expect(qs({})).toBe('')
  })
})

describe('seguridad de enlaces', () => {
  it('solo acepta http y https', () => {
    expect(urlSegura('https://infobras.contraloria.gob.pe/x?y=1')).toBe('https://infobras.contraloria.gob.pe/x?y=1')
    expect(urlSegura('javascript:alert(1)')).toBeNull()
    expect(urlSegura('data:text/html,<script>')).toBeNull()
    expect(urlSegura('no es una url')).toBeNull()
    expect(urlSegura(null)).toBeNull()
  })
})

describe('sesión', () => {
  it('el token vence en el cliente', () => {
    const t0 = Date.now()
    setToken('abc', 1)
    expect(getToken()).toBe('abc')
    vi.spyOn(Date, 'now').mockReturnValue(t0 + 2 * 60_000)
    expect(getToken()).toBeNull()
  })

  it('un 401 con sesión abierta cierra la sesión en toda la interfaz', async () => {
    const eventos = new EventTarget()
    vi.stubGlobal('window', eventos)
    const cerrada = vi.fn()
    eventos.addEventListener(SESION_EXPIRADA, cerrada)
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Token invalido' }), { status: 401 }))
    vi.stubGlobal('fetch', fetch)
    setToken('vencido', 10)
    await expect(api('/auth/me')).rejects.toMatchObject({ status: 401 })
    expect(fetch.mock.calls[0][1].headers.Authorization).toBe('Bearer vencido')
    expect(getToken()).toBeNull()
    expect(cerrada).toHaveBeenCalledOnce()
  })
})

describe('errores de la API en lenguaje claro', () => {
  it('traduce el código HTTP', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 429 })))
    await expect(api('/obras')).rejects.toThrow('Demasiadas solicitudes seguidas')
  })
  it('usa el detalle del servidor si el código no tiene mensaje propio', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Obra no encontrada' }), { status: 409 })))
    await expect(api('/obras/x')).rejects.toThrow('Obra no encontrada')
  })
  it('sin red devuelve estado 0', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const e = await api('/obras').catch((x: unknown) => x)
    expect(e).toBeInstanceOf(ApiError)
    expect((e as ApiError).status).toBe(0)
  })
})

describe('glosario', () => {
  it('todos los términos tienen nombre y definición', () => {
    for (const [k, v] of Object.entries(GLOSARIO)) {
      expect(v.termino.trim().length, k).toBeGreaterThan(1)
      expect(v.definicion.length, k).toBeGreaterThan(40)
    }
  })
})
