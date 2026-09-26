import { useQuery } from '@tanstack/react-query'
import { createContext, useContext, useState, type ReactNode } from 'react'
import { api } from './api'

interface Ctx {
  departamento: string | null
  setDepartamento: (d: string | null) => void
  opciones: { departamento: string; obras: number }[]
}

const AmbitoCtx = createContext<Ctx>({ departamento: null, setDepartamento: () => {}, opciones: [] })

function leer(): string | null {
  try {
    return localStorage.getItem('sato_ambito')
  } catch {
    return null
  }
}

export function AmbitoProvider({ children }: { children: ReactNode }) {
  const [departamento, set] = useState<string | null>(leer())
  const q = useQuery({ queryKey: ['ambitos'], queryFn: () => api<{ departamento: string; obras: number }[]>('/ambitos'), staleTime: Infinity })
  const setDepartamento = (d: string | null) => {
    set(d)
    try {
      if (d) localStorage.setItem('sato_ambito', d)
      else localStorage.removeItem('sato_ambito')
    } catch {
      /* almacenamiento no disponible */
    }
  }
  return <AmbitoCtx.Provider value={{ departamento, setDepartamento, opciones: q.data ?? [] }}>{children}</AmbitoCtx.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export const useAmbito = () => useContext(AmbitoCtx)
