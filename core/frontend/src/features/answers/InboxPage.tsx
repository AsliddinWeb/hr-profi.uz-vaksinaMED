import { useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { PageHeader } from '../../components/layout/PageHeader'
import { Card } from '../../components/ui/Card'
import { Input, Select } from '../../components/ui/Input'
import { Pagination } from '../../components/ui/Pagination'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { useCan } from '../auth/useAuth'
import { RequestList } from './RequestList'
import { STATUSES, type LeavePage } from './api'

const SIZE = 30

/** /answers/inbox: menga qaror kutayotgan so'rovlar (eng eskisi tepada) va (ko'rish huquqi bo'lsa) hamma so'rovlar. */
export function InboxPage() {
  const { t } = useTranslation()
  const can = useCan()
  const canDecide = can('answers.decide') || can('answers.manage')
  const canAll = can('answers.read') || can('answers.manage')
  const [tab, setTab] = useState<'inbox' | 'all'>(canDecide ? 'inbox' : 'all')
  const [status, setStatus] = useState('')
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const params = new URLSearchParams({ scope: tab, page: String(page), size: String(SIZE) })
  if (tab === 'all' && status) params.set('status', status)
  if (q.trim()) params.set('q', q.trim())
  const list = useQuery({ queryKey: ['answers', 'list', params.toString()], queryFn: () => api<LeavePage>(`/api/v1/answers/requests?${params}`), placeholderData: (p) => p, refetchInterval: 60_000 })
  const [now] = useState(() => Date.now())

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader title={t('answers.inbox.title')} subtitle={t('answers.inbox.subtitle')} />
      <Card className="flex flex-wrap items-center gap-3 p-4">
        {canDecide && canAll && (
          <div className="flex rounded-control bg-(--seg-bg) p-0.5 text-[13px]">
            {(['inbox', 'all'] as const).map((k) => (
              <button key={k} onClick={() => (setTab(k), setPage(1))} className={tab === k ? 'rounded-lg bg-(--seg-on) px-3 py-1.5 font-medium text-text shadow-card' : 'rounded-lg px-3 py-1.5 text-muted transition-colors hover:text-text'}>
                {t(`answers.inbox.tab.${k}`)}
              </button>
            ))}
          </div>
        )}
        <label className="relative min-w-36 max-w-64 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
          <Input className="pl-9" placeholder={t('schedule.searchEmployee')} value={q} onChange={(e) => (setQ(e.target.value), setPage(1))} aria-label={t('schedule.searchEmployee')} />
        </label>
        {tab === 'all' && (
          <Select className="w-auto" value={status} onChange={(e) => (setStatus(e.target.value), setPage(1))} aria-label={t('attendance.statusLabel')}>
            <option value="">{t('attendance.allStatuses')}</option>
            <option value="pending">{t('answers.inbox.pending')}</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {t(`answers.status.${s}`)}
              </option>
            ))}
          </Select>
        )}
      </Card>
      {list.isLoading ? <Skeleton className="h-40" /> : <RequestList items={list.data?.items ?? []} showEmployee now={now} empty={tab === 'inbox' ? t('answers.inbox.emptyInbox') : t('common.empty')} />}
      {list.data && list.data.total > SIZE && <Pagination page={page} size={SIZE} total={list.data.total} onPage={setPage} />}
    </div>
  )
}
