import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input, Select } from '../../components/ui/Input'
import { Pagination } from '../../components/ui/Pagination'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { useCan } from '../auth/useAuth'
import { dueText } from '../tasks/api'
import { PRIORITIES, PRIORITY_TONE, STATUS_TONE, STATUSES, type Category, type TicketPage } from './api'

const SIZE = 25
type Scope = 'mine' | 'assigned' | 'queue' | 'all'

/** /helpdesk: ticketlar (mening / menga biriktirilgan / navbat / hammasi). */
export function ListPage() {
  const { t } = useTranslation()
  const can = useCan()
  const staff = can('helpdesk.work') || can('helpdesk.read') || can('helpdesk.manage')
  const worker = can('helpdesk.work') || can('helpdesk.manage')
  const [scope, setScope] = useState<Scope>(worker ? 'queue' : 'mine')
  const [status, setStatus] = useState('open')
  const [category, setCategory] = useState('')
  const [priority, setPriority] = useState('')
  const [overdue, setOverdue] = useState(false)
  const [text, setText] = useState('')
  const [page, setPage] = useState(1)
  const params = new URLSearchParams({ scope, page: String(page), size: String(SIZE) })
  if (status && scope !== 'queue') params.set('status', status)
  if (category) params.set('category_id', category)
  if (priority) params.set('priority', priority)
  if (overdue) params.set('overdue', 'true')
  if (text.trim()) params.set('q', text.trim())
  const list = useQuery({ queryKey: ['helpdesk', 'list', params.toString()], queryFn: () => api<TicketPage>(`/api/v1/helpdesk?${params}`), placeholderData: (p) => p, refetchInterval: 30_000 })
  const cats = useQuery({ queryKey: ['helpdesk', 'categories'], queryFn: () => api<Category[]>('/api/v1/helpdesk/categories') })
  const reset = <T,>(fn: (v: T) => void) => (v: T) => (fn(v), setPage(1))
  const scopes: Scope[] = ['mine', ...(staff ? (['queue'] as const) : []), ...(worker ? (['assigned'] as const) : []), ...(staff ? (['all'] as const) : [])]

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <PageHeader
        title={t('helpdesk.title')}
        subtitle={t('helpdesk.subtitle')}
        actions={
          <Link to="/helpdesk/new">
            <Button>
              <Plus className="size-4" />
              {t('helpdesk.new')}
            </Button>
          </Link>
        }
      />
      <div className="flex flex-wrap items-center gap-3 rounded-card bg-surface p-3 shadow-card">
        {scopes.length > 1 && (
          <div className="flex rounded-control bg-(--seg-bg) p-0.5 text-[13px]" role="group">
            {scopes.map((s) => (
              <button key={s} onClick={() => reset(setScope)(s)} aria-pressed={scope === s} className={scope === s ? 'rounded-lg bg-(--seg-on) px-3 py-1.5 font-medium text-text shadow-card' : 'rounded-lg px-3 py-1.5 text-muted transition-colors hover:text-text'}>
                {t(`helpdesk.scope.${s}`)}
              </button>
            ))}
          </div>
        )}
        <Input className="w-48" value={text} onChange={(e) => reset(setText)(e.target.value)} placeholder={t('helpdesk.search')} aria-label={t('helpdesk.search')} />
        {scope !== 'queue' && (
          <Select className="w-auto" value={status} onChange={(e) => reset(setStatus)(e.target.value)} aria-label={t('attendance.statusLabel')}>
            <option value="">{t('attendance.allStatuses')}</option>
            <option value="open">{t('helpdesk.openOnes')}</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {t(`helpdesk.status.${s}`)}
              </option>
            ))}
          </Select>
        )}
        <Select className="w-auto" value={category} onChange={(e) => reset(setCategory)(e.target.value)} aria-label={t('helpdesk.category')}>
          <option value="">{t('helpdesk.allCategories')}</option>
          {cats.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>
        <Select className="w-auto" value={priority} onChange={(e) => reset(setPriority)(e.target.value)} aria-label={t('tasks.priorityLabel')}>
          <option value="">{t('helpdesk.allPriorities')}</option>
          {PRIORITIES.map((p) => (
            <option key={p} value={p}>
              {t(`tasks.priority.${p}`)}
            </option>
          ))}
        </Select>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" className="size-4" checked={overdue} onChange={(e) => reset(setOverdue)(e.target.checked)} />
          {t('helpdesk.overdueOnly')}
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
                  <th className="px-5 py-2.5 font-medium">{t('helpdesk.form.title')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('attendance.statusLabel')}</th>
                  <th className="hidden px-5 py-2.5 font-medium md:table-cell">{t('helpdesk.assignee')}</th>
                  <th className="hidden px-5 py-2.5 font-medium sm:table-cell">{t('tasks.priorityLabel')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('helpdesk.sla')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {list.data?.items.map((x) => (
                  <tr key={x.id}>
                    <td className="px-5 py-2.5">
                      <Link to={`/helpdesk/${x.id}`} className="font-medium hover:text-primary hover:underline">
                        {x.title}
                      </Link>
                      <div className="mt-0.5 text-xs text-muted">
                        {x.number}
                        {x.category?.name && ` · ${x.category.name}`}
                        {x.branch?.name && ` · ${x.branch.name}`}
                        {scope !== 'mine' && x.requester?.name && ` · ${x.requester.name}`}
                      </div>
                    </td>
                    <td className="px-5 py-2.5">
                      <Badge tone={STATUS_TONE[x.status]}>{t(`helpdesk.status.${x.status}`)}</Badge>
                      {x.reopen_count > 0 && <span className="ml-1.5 text-xs text-muted">↺{x.reopen_count}</span>}
                    </td>
                    <td className="hidden px-5 py-2.5 text-muted md:table-cell">{x.assignee?.name ?? '—'}</td>
                    <td className="hidden px-5 py-2.5 sm:table-cell">
                      <span className={`rounded-md px-2 py-0.5 text-xs font-medium ${PRIORITY_TONE[x.priority]}`}>{t(`tasks.priority.${x.priority}`)}</span>
                    </td>
                    <td className={'px-5 py-2.5 tabular-nums ' + (x.sla_breached ? 'font-semibold text-danger' : 'text-muted')}>{x.due_at && ['new', 'in_progress', 'waiting'].includes(x.status) ? dueText(x.due_at) : x.sla_breached ? t('helpdesk.breached') : '—'}</td>
                  </tr>
                ))}
                {list.data && list.data.items.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-5 py-10 text-center text-muted">
                      {t('common.empty')}
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
