import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../../components/layout/PageHeader'
import { Badge } from '../../../components/ui/Badge'
import { Button } from '../../../components/ui/Button'
import { Card } from '../../../components/ui/Card'
import { Pagination } from '../../../components/ui/Pagination'
import { Skeleton } from '../../../components/ui/Skeleton'
import { api } from '../../../lib/api'
import { formatDate } from '../../../lib/format'
import { useCan } from '../../auth/useAuth'
import { ISSUE_STATUSES, ISSUE_TONE, type IssuePage } from './api'

const SIZE = 20

/** /attendance/issues: o'z so'rovlarim va (koordinator/HR uchun) qaror kutayotganlar. */
export function IssuesPage() {
  const { t, i18n } = useTranslation()
  const can = useCan()
  const canReview = can('attendance.edit') || can('answers.decide') || can('attendance.read')
  const [scope, setScope] = useState<'mine' | 'inbox'>(canReview ? 'inbox' : 'mine')
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const params = new URLSearchParams({ scope, page: String(page), size: String(SIZE) })
  if (status) params.set('status', status)
  const list = useQuery({ queryKey: ['attendance-issues', params.toString()], queryFn: () => api<IssuePage>(`/api/v1/attendance-issues?${params}`), placeholderData: (p) => p, refetchInterval: 60_000 })
  const pill = (active: boolean) => 'rounded-full border px-3 py-1.5 text-xs font-medium ' + (active ? 'border-primary bg-primary text-primary-fg' : 'border-border bg-surface text-muted hover:text-text')

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title={t('attendance.issue.title')}
        subtitle={t('attendance.issue.subtitle')}
        actions={
          can('attendance.punch') && (
            <Link to="/attendance/issues/new">
              <Button>
                <Plus className="size-4" />
                {t('attendance.issue.new')}
              </Button>
            </Link>
          )
        }
      />
      {canReview && (
        <div className="flex gap-2" role="group">
          {(['inbox', 'mine'] as const).map((s) => (
            <button key={s} aria-pressed={scope === s} onClick={() => (setScope(s), setPage(1))} className={pill(scope === s)}>
              {t(`attendance.issue.${s}`)}
            </button>
          ))}
        </div>
      )}
      {scope === 'mine' && (
        <div className="flex flex-wrap gap-2" role="group" aria-label={t('attendance.statusLabel')}>
          {['', ...ISSUE_STATUSES].map((s) => (
            <button key={s} aria-pressed={status === s} onClick={() => (setStatus(s), setPage(1))} className={pill(status === s)}>
              {s ? t(`attendance.issue.status.${s}`) : t('attendance.allStatuses')}
            </button>
          ))}
        </div>
      )}
      {list.isLoading ? (
        <Skeleton className="h-40" />
      ) : (
        <div className="flex flex-col gap-3">
          {list.data?.items.map((i) => (
            <Link key={i.id} to={`/attendance/issues/${i.id}`}>
              <Card className="flex flex-wrap items-center justify-between gap-3 p-4 hover:bg-surface-2">
                <div className="min-w-0">
                  <div className="font-medium">{i.employee.full_name}</div>
                  <div className="text-sm text-muted">
                    {formatDate(i.work_date, i18n.language)} · {t(`attendance.issue.kind.${i.kind}`)} · {t(`attendance.issue.method.${i.method_tried}`)}
                    {i.branch ? ` · ${i.branch}` : ''}
                  </div>
                </div>
                <Badge tone={ISSUE_TONE[i.status]}>{t(`attendance.issue.status.${i.status}`)}</Badge>
              </Card>
            </Link>
          ))}
          {list.data && list.data.items.length === 0 && <Card className="p-8 text-center text-muted">{t('attendance.issue.empty')}</Card>}
        </div>
      )}
      {list.data && list.data.total > SIZE && <Pagination page={page} size={SIZE} total={list.data.total} onPage={setPage} />}
    </div>
  )
}
