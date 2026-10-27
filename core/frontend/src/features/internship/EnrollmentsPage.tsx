import { useQuery } from '@tanstack/react-query'
import { UserPlus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Select } from '../../components/ui/Input'
import { Pagination } from '../../components/ui/Pagination'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { useCan } from '../auth/useAuth'
import { ESTATUS_TONE, type Enrollment, type Page } from './api'

const SIZE = 25
type Scope = 'mine' | 'mentor' | 'all'

/** /internship: stajirovkalar (mening / mening stajyorlarim / hammasi). */
export function EnrollmentsPage() {
  const { t, i18n } = useTranslation()
  const can = useCan()
  const all = can('internship.read') || can('internship.manage')
  const manage = can('internship.manage')
  const [scope, setScope] = useState<Scope>(all ? 'all' : 'mine')
  const [status, setStatus] = useState('open')
  const [page, setPage] = useState(1)
  const params = new URLSearchParams({ scope, page: String(page), size: String(SIZE) })
  if (status) params.set('status', status)
  const q = useQuery({ queryKey: ['internship', 'list', params.toString()], queryFn: () => api<Page<Enrollment>>(`/api/v1/internship/enrollments?${params}`), placeholderData: (p) => p })
  const scopes: Scope[] = ['mine', 'mentor', ...(all ? (['all'] as const) : [])]

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <PageHeader
        title={t('internship.title')}
        subtitle={t('internship.subtitle')}
        actions={
          manage && (
            <Link to="/internship/enrollments/new">
              <Button>
                <UserPlus className="size-4" />
                {t('internship.enroll.add')}
              </Button>
            </Link>
          )
        }
      />
      <div className="flex flex-wrap items-center gap-3 rounded-card bg-surface p-3 shadow-card">
        <div className="flex rounded-control bg-(--seg-bg) p-0.5 text-[13px]" role="group">
          {scopes.map((s) => (
            <button key={s} onClick={() => (setScope(s), setPage(1))} aria-pressed={scope === s} className={scope === s ? 'rounded-lg bg-(--seg-on) px-3 py-1.5 font-medium text-text shadow-card' : 'rounded-lg px-3 py-1.5 text-muted transition-colors hover:text-text'}>
              {t(`internship.scope.${s}`)}
            </button>
          ))}
        </div>
        <Select className="w-auto" value={status} onChange={(e) => (setStatus(e.target.value), setPage(1))} aria-label={t('attendance.statusLabel')}>
          <option value="open">{t('internship.openOnes')}</option>
          <option value="">{t('attendance.allStatuses')}</option>
          {(['active', 'ready', 'completed', 'cancelled'] as const).map((s) => (
            <option key={s} value={s}>
              {t(`internship.status.${s}`)}
            </option>
          ))}
        </Select>
        <Link to="/internship/programs" className="ml-auto text-sm text-primary hover:underline">
          {t('internship.programs.title')}
        </Link>
      </div>
      {q.isLoading ? (
        <Skeleton className="h-48" />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {q.data?.items.map((e) => (
            <Link key={e.id} to={`/internship/enrollments/${e.id}`}>
              <Card className="flex h-full flex-col gap-3 p-5 transition-shadow hover:shadow-card">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="font-semibold">{e.employee.name}</h2>
                    <p className="text-sm text-muted">{e.program.name}</p>
                  </div>
                  <Badge tone={ESTATUS_TONE[e.status]}>{t(`internship.status.${e.status}`)}</Badge>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-surface-2" role="progressbar" aria-valuenow={e.progress.percent} aria-valuemin={0} aria-valuemax={100}>
                  <div className="h-full rounded-full bg-primary" style={{ width: `${e.progress.percent}%` }} />
                </div>
                <div className="flex flex-wrap justify-between gap-2 text-xs text-muted tabular-nums">
                  <span>
                    {e.progress.done}/{e.progress.required} · {e.progress.percent}%
                  </span>
                  {e.progress.avg_score !== null && <span>{t('internship.avgScore')}: {e.progress.avg_score}%</span>}
                  {e.due_date && <span className={e.overdue ? 'font-semibold text-danger' : ''}>{formatDate(e.due_date, i18n.language)}</span>}
                </div>
              </Card>
            </Link>
          ))}
          {q.data?.items.length === 0 && <p className="col-span-full py-10 text-center text-muted">{t('common.empty')}</p>}
        </div>
      )}
      {q.data && q.data.total > SIZE && <Pagination page={page} size={SIZE} total={q.data.total} onPage={setPage} />}
    </div>
  )
}
