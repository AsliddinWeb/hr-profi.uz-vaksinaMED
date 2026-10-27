import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Pagination } from '../../components/ui/Pagination'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { RequestList } from './RequestList'
import { STATUSES, type LeavePage } from './api'

const SIZE = 20

/** /answers: xodimning o'z so'rovlari va ularning holati. */
export function MyRequestsPage() {
  const { t } = useTranslation()
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const params = new URLSearchParams({ scope: 'mine', page: String(page), size: String(SIZE) })
  if (status) params.set('status', status)
  const list = useQuery({ queryKey: ['answers', 'mine', params.toString()], queryFn: () => api<LeavePage>(`/api/v1/answers/requests?${params}`), placeholderData: (p) => p, refetchInterval: 60_000 })
  const [now] = useState(() => Date.now())

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title={t('answers.my.title')}
        subtitle={t('answers.my.subtitle')}
        actions={
          <Link to="/answers/new">
            <Button>
              <Plus className="size-4" />
              {t('answers.new')}
            </Button>
          </Link>
        }
      />
      <div className="flex flex-wrap gap-2" role="group" aria-label={t('attendance.statusLabel')}>
        {['', ...STATUSES].map((s) => (
          <button key={s} onClick={() => (setStatus(s), setPage(1))} aria-pressed={status === s} className={'rounded-full border px-3 py-1.5 text-xs font-medium ' + (status === s ? 'border-primary bg-primary text-primary-fg' : 'border-border bg-surface text-muted hover:text-text')}>
            {s ? t(`answers.status.${s}`) : t('attendance.allStatuses')}
          </button>
        ))}
      </div>
      {list.isLoading ? <Skeleton className="h-40" /> : <RequestList items={list.data?.items ?? []} now={now} empty={t('answers.my.empty')} />}
      {list.data && list.data.total > SIZE && <Pagination page={page} size={SIZE} total={list.data.total} onPage={setPage} />}
    </div>
  )
}
