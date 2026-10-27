import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { ListChecks } from 'lucide-react'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/EmptyState'
import { Select } from '../../components/ui/Input'
import { Pagination } from '../../components/ui/Pagination'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { Filters } from './Filters'
import { defaultFilter, filterQuery, type TaskFilter } from './filterState'
import { ViewTabs } from './ViewTabs'
import { dueText, PRIORITY_TONE, STATUSES, type TaskPage } from './api'

const SIZE = 30

/** /tasks: topshiriqlar ro'yxati (filtr, saralash). */
export function ListPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [filter, setFilter] = useState<TaskFilter>(defaultFilter)
  const [status, setStatus] = useState('open')
  const [sort, setSort] = useState('due')
  const [overdue, setOverdue] = useState(false)
  const [page, setPage] = useState(1)
  const params = new URLSearchParams({ page: String(page), size: String(SIZE), sort })
  filterQuery(filter, params)
  if (status) params.set('status', status)
  if (overdue) params.set('overdue', 'true')
  const list = useQuery({ queryKey: ['tasks', 'list', params.toString()], queryFn: () => api<TaskPage>(`/api/v1/tasks?${params}`), placeholderData: (p) => p })
  const reset = <T,>(fn: (v: T) => void) => (v: T) => (fn(v), setPage(1))

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <PageHeader title={t('tasks.title')} subtitle={t('tasks.subtitle')} actions={<ViewTabs />} />
      <div className="flex flex-wrap items-center gap-3 rounded-card bg-surface p-3 shadow-card">
        <Filters value={filter} onChange={reset(setFilter)} />
        <Select className="w-auto" value={status} onChange={(e) => reset(setStatus)(e.target.value)} aria-label={t('attendance.statusLabel')}>
          <option value="">{t('attendance.allStatuses')}</option>
          <option value="open">{t('tasks.openOnes')}</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {t(`tasks.status.${s}`)}
            </option>
          ))}
        </Select>
        <Select className="w-auto" value={sort} onChange={(e) => reset(setSort)(e.target.value)} aria-label={t('tasks.sort.label')}>
          {['due', 'created', 'priority'].map((k) => (
            <option key={k} value={k}>
              {t(`tasks.sort.${k}`)}
            </option>
          ))}
        </Select>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" className="size-4" checked={overdue} onChange={(e) => reset(setOverdue)(e.target.checked)} />
          {t('tasks.overdueOnly')}
        </label>
      </div>
      {list.isLoading ? (
        <Skeleton className="h-48" />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border text-xs text-muted">
                <tr>
                  <th className="px-5 py-2.5 font-medium">{t('tasks.form.title')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('attendance.statusLabel')}</th>
                  <th className="hidden px-5 py-2.5 font-medium md:table-cell">{t('tasks.assignee')}</th>
                  <th className="hidden px-5 py-2.5 font-medium sm:table-cell">{t('tasks.priorityLabel')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('tasks.due')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {list.data?.items.map((x) => (
                  <tr key={x.id} data-href onClick={(ev) => !(ev.target as HTMLElement).closest('a,button,input') && navigate(`/tasks/${x.id}`)}>
                    <td className="px-5 py-2.5">
                      <Link to={`/tasks/${x.id}`} className="font-medium hover:text-primary hover:underline">
                        {x.title}
                      </Link>
                      {x.labels.length > 0 && <div className="mt-0.5 text-xs text-muted">{x.labels.join(' · ')}</div>}
                    </td>
                    <td className="px-5 py-2.5">
                      <Badge tone={x.status === 'done' ? 'success' : x.status === 'review' ? 'warning' : 'neutral'}>{t(`tasks.status.${x.status}`)}</Badge>
                    </td>
                    <td className="hidden px-5 py-2.5 text-muted md:table-cell">{x.assignee?.name ?? '—'}</td>
                    <td className="hidden px-5 py-2.5 sm:table-cell">
                      <span className={`rounded-md px-2 py-0.5 text-xs font-medium ${PRIORITY_TONE[x.priority]}`}>{t(`tasks.priority.${x.priority}`)}</span>
                    </td>
                    <td className={'px-5 py-2.5 tabular-nums ' + (x.overdue ? 'font-semibold text-danger' : 'text-muted')}>{x.due_at ? dueText(x.due_at) : '—'}</td>
                  </tr>
                ))}
                {list.data && list.data.items.length === 0 && (
                  <tr>
                    <td colSpan={5}>
                      <EmptyState icon={ListChecks} title={t('tasks.emptyTitle')} hint={t('tasks.emptyHint')} />
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}
      {list.data && list.data.total > SIZE && <Pagination page={page} size={SIZE} total={list.data.total} onPage={setPage} />}
    </div>
  )
}
