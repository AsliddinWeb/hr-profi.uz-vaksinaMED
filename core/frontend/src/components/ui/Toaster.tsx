import { cn } from '../../lib/cn'
import { X } from 'lucide-react'
import { useCallback, useMemo, useState, type ReactNode } from 'react'

import { ToastContext, type Toast } from './toastContext'

const tones = {
  info: 'border-l-info',
  success: 'border-l-success',
  warning: 'border-l-warning',
  danger: 'border-l-danger',
}

let nextId = 1

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const dismiss = useCallback((id: number) => setToasts((l) => l.filter((t) => t.id !== id)), [])
  const push = useCallback(
    (t: Omit<Toast, 'id'>) => {
      const id = nextId++
      setToasts((l) => [...l.slice(-3), { ...t, id }])
      setTimeout(() => dismiss(id), 7000)
    },
    [dismiss],
  )
  const value = useMemo(() => ({ push }), [push])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-[min(22rem,calc(100vw-2rem))] flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={cn(
              'rise pointer-events-auto flex items-start gap-3 rounded-card border-l-[3px] bg-surface p-4 shadow-pop',
              tones[t.tone ?? 'info'],
              t.onClick && 'cursor-pointer',
            )}
            onClick={() => {
              t.onClick?.()
              dismiss(t.id)
            }}
          >
            <div className="min-w-0 flex-1">
              <div className="text-sm font-semibold">{t.title}</div>
              {t.body && <div className="mt-0.5 line-clamp-3 text-sm text-muted">{t.body}</div>}
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation()
                dismiss(t.id)
              }}
              aria-label="×"
              className="rounded p-1 text-muted hover:bg-surface-2"
            >
              <X className="size-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
