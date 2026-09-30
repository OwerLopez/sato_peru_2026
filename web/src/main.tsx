import '@fontsource-variable/lexend'
import '@fontsource-variable/source-sans-3'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Tooltip } from 'radix-ui'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { AmbitoProvider } from './ambito'
import { ApiError } from './api'
import { AuthProvider } from './auth'
import './index.css'

const qc = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      // no reintentar errores del cliente (404, 422, 429): solo fallas de red o del servidor
      retry: (n, e) => n < 1 && !(e instanceof ApiError && e.status >= 400 && e.status < 500),
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={qc}>
      <Tooltip.Provider>
        <AuthProvider>
          <AmbitoProvider>
            <BrowserRouter basename={import.meta.env.BASE_URL.replace(/\/$/, '')}>
              <App />
            </BrowserRouter>
          </AmbitoProvider>
        </AuthProvider>
      </Tooltip.Provider>
    </QueryClientProvider>
  </StrictMode>,
)
