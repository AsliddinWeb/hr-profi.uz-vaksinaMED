import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'

import { ConfirmProvider } from './components/ui/ConfirmProvider'
import { ToastProvider } from './components/ui/Toaster'

import './index.css'
import { loadClientExtension } from './extensions'
import './lib/i18n'
import { applyTheme } from './lib/theme'
import { createRouter } from './router'

applyTheme()
// Tizim mavzusi o'zgarsa (rejim 'system' bo'lganda) yangilanadi
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => applyTheme())

// Mijoz extension router yaratilishidan OLDIN yuklanishi kerak (marshrutlar qo'shadi)
loadClientExtension()

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <ConfirmProvider>
          <RouterProvider router={createRouter()} />
        </ConfirmProvider>
      </ToastProvider>
    </QueryClientProvider>
  </StrictMode>,
)
