import { useQuery } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
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
  const setDepartamento = useCallback((d: string | null) => {
    set(d)
    try {
      if (d) localStorage.setItem('sato_ambito', d)
      else localStorage.removeItem('sato_ambito')
    } catch {
      /* almacenamiento no disponible */
    }
  }, [])
  const opciones = q.data
  const valor = useMemo(() => ({ departamento, setDepartamento, opciones: opciones ?? [] }), [departamento, setDepartamento, opciones])
  return <AmbitoCtx.Provider value={valor}>{children}</AmbitoCtx.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export const useAmbito = () => useContext(AmbitoCtx)
