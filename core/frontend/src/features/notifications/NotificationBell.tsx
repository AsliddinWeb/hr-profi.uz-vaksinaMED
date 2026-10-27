import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { api, send } from '../../lib/api'
import type { NotificationPage } from './api'
import { NotificationItemRow } from './NotificationItemRow'
import { useOpenNotification, useUnread } from './useNotifications'

export function NotificationBell() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const unread = useUnread()
  const openItem = useOpenNotification()

  const recent = useQuery({
    queryKey: ['notifications', 'recent'],
    queryFn: () => api<NotificationPage>('/api/v1/notifications?size=8'),
    enabled: open,
  })
  const readAll = useMutation({
    mutationFn: () => send('POST', '/api/v1/notifications/read-all'),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['notifications'] })
      void qc.invalidateQueries({ queryKey: ['unread'] })
    },
  })

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false)
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const count = unread.data?.count ?? 0

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label={t('notifications.title')}
        aria-expanded={open}
        className="relative grid size-10 cursor-pointer place-items-center rounded-xl bg-surface shadow-card transition-all hover:-translate-y-px hover:shadow-pop"
      >
        <Bell className="size-[18px] text-(--c-amber)" />
        {count > 0 && (
          <span className="absolute -right-1 -top-1 grid min-w-[18px] place-items-center rounded-full bg-danger px-1 text-[10px] font-medium leading-[18px] text-white ring-2 ring-bg">
            {count > 99 ? '99+' : count}
          </span>
        )}
      </button>

      {open && (
        <div className="rise absolute right-0 z-30 mt-2 w-[min(24rem,calc(100vw-2rem))] rounded-card bg-surface p-2 shadow-pop">
          <div className="flex items-center justify-between px-3 py-2">
            <span className="text-[13px] font-medium">{t('notifications.title')}</span>
            {count > 0 && (
              <button onClick={() => readAll.mutate()} className="text-xs font-medium text-primary hover:underline">
                {t('notifications.readAll')}
              </button>
            )}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {recent.data?.items.map((n) => (
              <NotificationItemRow
                key={n.id}
                n={n}
                onOpen={(item) => {
                  setOpen(false)
                  openItem(item)
                }}
              />
            ))}
            {recent.data && recent.data.items.length === 0 && (
              <p className="px-3 py-8 text-center text-sm text-muted">{t('notifications.empty')}</p>
            )}
          </div>
          <Link
            to="/notifications"
            onClick={() => setOpen(false)}
            className="mt-1 block rounded-control px-3 py-2 text-center text-sm font-medium text-primary hover:bg-surface-2"
          >
            {t('notifications.viewAll')}
          </Link>
        </div>
      )}
    </div>
  )
}
