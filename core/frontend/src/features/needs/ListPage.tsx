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
import { PRIORITY_TONE, STATUS_TONE, type Category, type NeedPage } from './api'

const SIZE = 25
type Scope = 'mine' | 'assigned' | 'all'

/** /needs: ehtiyojlar ro'yxati (mening so'rovlarim / menga biriktirilgan / hammasi). */
export function ListPage() {
  const { t } = useTranslation()
  const can = useCan()
  const dispatch = can('needs.dispatch') || can('needs.manage')
  const worker = can('needs.work') || dispatch
  const [scope, setScope] = useState<Scope>('mine')
  const [status, setStatus] = useState('open')
  const [category, setCategory] = useState('')
  const [overdue, setOverdue] = useState(false)
  const [text, setText] = useState('')
  const [page, setPage] = useState(1)
  const params = new URLSearchParams({ scope, page: String(page), size: String(SIZE) })
  if (status) params.set('status', status)
  if (category) params.set('category_id', category)
  if (overdue) params.set('overdue', 'true')
  if (text.trim()) params.set('q', text.trim())
  const list = useQuery({ queryKey: ['needs', 'list', params.toString()], queryFn: () => api<NeedPage>(`/api/v1/needs?${params}`), placeholderData: (p) => p })
  const cats = useQuery({ queryKey: ['needs', 'categories'], queryFn: () => api<Category[]>('/api/v1/needs/categories') })
  const reset = <T,>(fn: (v: T) => void) => (v: T) => (fn(v), setPage(1))
  const scopes: Scope[] = ['mine', ...(worker ? (['assigned'] as const) : []), ...(dispatch ? (['all'] as const) : [])]

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <PageHeader
        title={t('needs.title')}
        subtitle={t('needs.subtitle')}
        actions={
          <Link to="/needs/new">
            <Button>
              <Plus className="size-4" />
              {t('needs.new')}
            </Button>
          </Link>
        }
      />
      <div className="flex flex-wrap items-center gap-3 rounded-card bg-surface p-3 shadow-card">
        {scopes.length > 1 && (
          <div className="flex rounded-control bg-(--seg-bg) p-0.5 text-[13px]" role="group">
            {scopes.map((s) => (
              <button key={s} onClick={() => reset(setScope)(s)} aria-pressed={scope === s} className={scope === s ? 'rounded-lg bg-(--seg-on) px-3 py-1.5 font-medium text-text shadow-card' : 'rounded-lg px-3 py-1.5 text-muted transition-colors hover:text-text'}>
                {t(`needs.scope.${s}`)}
              </button>
            ))}
          </div>
        )}
        <Input className="w-48" value={text} onChange={(e) => reset(setText)(e.target.value)} placeholder={t('needs.search')} aria-label={t('needs.search')} />
        <Select className="w-auto" value={status} onChange={(e) => reset(setStatus)(e.target.value)} aria-label={t('attendance.statusLabel')}>
          <option value="">{t('attendance.allStatuses')}</option>
          <option value="open">{t('needs.openOnes')}</option>
          {(['requested', 'assigned', 'completed', 'confirmed', 'cancelled'] as const).map((s) => (
            <option key={s} value={s}>
              {t(`needs.status.${s}`)}
            </option>
          ))}
        </Select>
        <Select className="w-auto" value={category} onChange={(e) => reset(setCategory)(e.target.value)} aria-label={t('needs.category')}>
          <option value="">{t('needs.allCategories')}</option>
          {cats.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" className="size-4" checked={overdue} onChange={(e) => reset(setOverdue)(e.target.checked)} />
          {t('needs.overdueOnly')}
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
                  <th className="px-5 py-2.5 font-medium">{t('needs.form.title')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('attendance.statusLabel')}</th>
                  <th className="hidden px-5 py-2.5 font-medium md:table-cell">{t('needs.assignee')}</th>
                  <th className="hidden px-5 py-2.5 font-medium sm:table-cell">{t('tasks.priorityLabel')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('needs.due')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {list.data?.items.map((x) => (
                  <tr key={x.id}>
                    <td className="px-5 py-2.5">
                      <Link to={`/needs/${x.id}`} className="font-medium hover:text-primary hover:underline">
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
                      <Badge tone={STATUS_TONE[x.status]}>{t(`needs.status.${x.status}`)}</Badge>
                      {x.return_count > 0 && <span className="ml-1.5 text-xs text-muted">↺{x.return_count}</span>}
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
