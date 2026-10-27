import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Send } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'

import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Pagination } from '../../components/ui/Pagination'
import { Skeleton } from '../../components/ui/Skeleton'
import { api, send } from '../../lib/api'
import { useCan } from '../auth/useAuth'
import type { NotificationPage } from './api'
import { NotificationItemRow } from './NotificationItemRow'
import { useOpenNotification } from './useNotifications'

const SIZE = 20

export function NotificationsPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const can = useCan()
  const [unreadOnly, setUnreadOnly] = useState(false)
  const [page, setPage] = useState(1)
  const open = useOpenNotification()

  const list = useQuery({
    queryKey: ['notifications', 'list', unreadOnly, page],
    queryFn: () => api<NotificationPage>(`/api/v1/notifications?page=${page}&size=${SIZE}${unreadOnly ? '&unread=true' : ''}`),
    placeholderData: (prev) => prev,
  })
  const readAll = useMutation({
    mutationFn: () => send('POST', '/api/v1/notifications/read-all'),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['notifications'] })
      void qc.invalidateQueries({ queryKey: ['unread'] })
    },
  })

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader
        title={t('notifications.title')}
        subtitle={t('notifications.subtitle')}
        actions={
          <>
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

      <div className="flex gap-2">
        {[false, true].map((u) => (
          <button
            key={String(u)}
            onClick={() => {
              setUnreadOnly(u)
              setPage(1)
            }}
            className={
              unreadOnly === u
                ? 'rounded-control bg-primary px-4 py-2 text-sm font-medium text-primary-fg'
                : 'rounded-control border border-border bg-surface px-4 py-2 text-sm text-muted hover:text-text'
            }
          >
            {u ? t('notifications.unread') : t('notifications.all')}
          </button>
        ))}
      </div>

      <Card className="p-2">
        {list.isLoading && <Skeleton className="m-2 h-32" />}
        {list.data?.items.map((n) => <NotificationItemRow key={n.id} n={n} onOpen={open} />)}
        {list.data && list.data.items.length === 0 && (
          <p className="px-3 py-10 text-center text-sm text-muted">{t('notifications.empty')}</p>
        )}
        {list.data && list.data.total > SIZE && (
          <div className="border-t border-border px-3 pb-1 pt-3">
            <Pagination page={page} size={SIZE} total={list.data.total} onPage={setPage} />
          </div>
        )}
      </Card>

    </div>
  )
}
