import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Send, Settings } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api, send } from '../../lib/api'
import { useCan } from '../auth/useAuth'
import type { NotificationPage, PrefsResponse } from './api'
import { catLabel } from './api'
import { NotificationItemRow } from './NotificationItemRow'
import { useOpenNotification } from './useNotifications'

const STEP = 30

function dayKey(iso: string): string {
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/** /notifications: kunlar bo'yicha guruhlangan, toifa va o'qilmagan bo'yicha filtrlanadigan markaz. */
export function NotificationsPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const can = useCan()
  const [unreadOnly, setUnreadOnly] = useState(false)
  const [category, setCategory] = useState('')
  const [size, setSize] = useState(STEP)
  const [[today, yesterday]] = useState(() => [dayKey(new Date().toISOString()), dayKey(new Date(Date.now() - 86400000).toISOString())])
  const open = useOpenNotification()

  const prefs = useQuery({ queryKey: ['notifications', 'prefs'], queryFn: () => api<PrefsResponse>('/api/v1/notifications/preferences'), refetchInterval: 60_000 })
  const list = useQuery({
    queryKey: ['notifications', 'list', unreadOnly, category, size],
    queryFn: () => api<NotificationPage>(`/api/v1/notifications?page=1&size=${size}${unreadOnly ? '&unread=true' : ''}${category ? `&category=${category}` : ''}`),
    placeholderData: (prev) => prev,
  })
  const readAll = useMutation({
    mutationFn: () => send('POST', '/api/v1/notifications/read-all'),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['notifications'] })
      void qc.invalidateQueries({ queryKey: ['unread'] })
    },
  })
  const groups = useMemo(() => {
    const out: { key: string; items: NotificationPage['items'] }[] = []
    for (const n of list.data?.items ?? []) {
      const k = dayKey(n.created_at)
      const last = out[out.length - 1]
      if (last && last.key === k) last.items.push(n)
      else out.push({ key: k, items: [n] })
    }
    return out
  }, [list.data])
  const label = (k: string) => (k === today ? t('notifications.today') : k === yesterday ? t('notifications.yesterday') : k.split('-').reverse().join('.'))
  const pill = (on: boolean) => 'inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium ' + (on ? 'border-primary bg-primary text-primary-fg' : 'border-border bg-surface text-muted hover:text-text')
  const cats = (prefs.data?.categories ?? []).filter((c) => c.unread > 0 || c.key === category)

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <PageHeader
        title={t('notifications.title')}
        subtitle={t('notifications.subtitle')}
        actions={
          <>
            <Link to="/notifications/settings">
              <Button variant="outline">
                <Settings className="size-4" />
                {t('notifications.settings')}
              </Button>
            </Link>
            <Button variant="outline" onClick={() => readAll.mutate()} disabled={readAll.isPending}>
              {t('notifications.readAll')}
            </Button>
            {can('notifications.send') && (
              <Link to="/notifications/send">
                <Button>
                  <Send className="size-4" />
                  {t('notifications.broadcast')}
                </Button>
              </Link>
            )}
          </>
        }
      />

      <div className="flex flex-wrap gap-2">
        {[false, true].map((u) => (
          <button key={String(u)} aria-pressed={unreadOnly === u} onClick={() => (setUnreadOnly(u), setSize(STEP))} className={pill(unreadOnly === u)}>
            {u ? t('notifications.unread') : t('notifications.all')}
          </button>
        ))}
        <span className="mx-1 w-px self-stretch bg-border" />
        <button aria-pressed={category === ''} onClick={() => (setCategory(''), setSize(STEP))} className={pill(category === '')}>
          {t('notifications.allCats')}
        </button>
        {cats.map((c) => (
          <button key={c.key} aria-pressed={category === c.key} onClick={() => (setCategory(c.key), setSize(STEP))} className={pill(category === c.key)}>
            {catLabel(t, c.key)}
            {c.unread > 0 && <span className="rounded-full bg-danger px-1.5 text-[10px] text-white">{c.unread}</span>}
          </button>
        ))}
      </div>

      {list.isLoading && <Skeleton className="h-40" />}
      {groups.map((g) => (
        <section key={g.key} className="flex flex-col gap-1.5">
          <h2 className="px-1 text-xs font-semibold uppercase tracking-wide text-muted">
            {label(g.key)} · {g.items.length}
          </h2>
          <Card className="p-2">
            {g.items.map((n) => (
              <NotificationItemRow key={n.id} n={n} onOpen={open} />
            ))}
          </Card>
        </section>
      ))}
      {list.data && list.data.items.length === 0 && <Card className="px-3 py-10 text-center text-sm text-muted">{t('notifications.empty')}</Card>}
      {list.data && list.data.total > list.data.items.length && (
        <Button variant="outline" onClick={() => setSize(size + STEP)}>
          {t('notifications.more', { n: list.data.total - list.data.items.length })}
        </Button>
      )}
    </div>
  )
}
