import { createContext, useContext } from 'react'

export interface Toast {
  id: number
  title: string
  body?: string | null
  tone?: 'info' | 'success' | 'warning' | 'danger'
  onClick?: () => void
}

interface Ctx {
  push: (t: Omit<Toast, 'id'>) => void
}

export const ToastContext = createContext<Ctx>({ push: () => {} })
export const useToast = () => useContext(ToastContext)
