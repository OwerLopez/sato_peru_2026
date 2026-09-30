import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, getToken, SESION_EXPIRADA, setToken } from './api'

export interface Usuario {
  id: number
  email: string
  nombre: string
  rol: 'analista' | 'admin'
}

interface Ctx {
  usuario: Usuario | null
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthCtx = createContext<Ctx>({ usuario: null, login: async () => {}, logout: () => {} })

export function AuthProvider({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null)
  useEffect(() => {
    if (getToken()) api<Usuario>('/auth/me').then(setUsuario).catch(() => setToken(null))
    const cerrar = () => setUsuario(null)
    window.addEventListener(SESION_EXPIRADA, cerrar)
    return () => window.removeEventListener(SESION_EXPIRADA, cerrar)
  }, [])
  const login = useCallback(async (email: string, password: string) => {
    const r = await api<{ access_token: string; expira_en_min: number; usuario: Usuario }>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })
    setToken(r.access_token, r.expira_en_min)
    setUsuario(r.usuario)
  }, [])
  const logout = useCallback(() => {
    setToken(null)
    setUsuario(null)
  }, [])
  const valor = useMemo(() => ({ usuario, login, logout }), [usuario, login, logout])
  return <AuthCtx.Provider value={valor}>{children}</AuthCtx.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => useContext(AuthCtx)
