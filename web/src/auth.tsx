import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, getToken, setToken } from './api'

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
  }, [])
  const login = async (email: string, password: string) => {
    const r = await api<{ access_token: string; usuario: Usuario }>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })
    setToken(r.access_token)
    setUsuario(r.usuario)
  }
  const logout = () => {
    setToken(null)
    setUsuario(null)
  }
  return <AuthCtx.Provider value={{ usuario, login, logout }}>{children}</AuthCtx.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => useContext(AuthCtx)
