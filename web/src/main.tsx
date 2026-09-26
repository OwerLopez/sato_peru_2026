import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { AmbitoProvider } from './ambito'
import { AuthProvider } from './auth'
import './index.css'

const qc = new QueryClient({ defaultOptions: { queries: { staleTime: 5 * 60_000, retry: 1, refetchOnWindowFocus: false } } })

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={qc}>
      <AuthProvider>
        <AmbitoProvider>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </AmbitoProvider>
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
)
