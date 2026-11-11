import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { LogIn, LogOut, Plus } from 'lucide-react'
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
import { api, send } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import { STATUS_TONE, STATUSES, type VisitPage } from './api'

const SIZE = 25
type Scope = 'mine' | 'all'

/** /reception: mehmonlar jurnali. Resepshin: hozir ichkarida, kelishi kutilayotganlar, tezkor kirish/chiqish. */
export function ListPage() {
  const { t, i18n } = useTranslation()
  const can = useCan()
  const qc = useQueryClient()
  const viewer = can('reception.desk') || can('reception.read')
  const desk = can('reception.desk')
  const [scope, setScope] = useState<Scope>(viewer ? 'all' : 'mine')
  const [status, setStatus] = useState(viewer ? 'open' : '')
  const [date, setDate] = useState('')
  const [text, setText] = useState('')
  const [page, setPage] = useState(1)
  const params = new URLSearchParams({ scope, page: String(page), size: String(SIZE) })
  if (status) params.set('status', status)
  if (date) params.set('date', date)
  if (text.trim()) params.set('q', text.trim())
  const list = useQuery({ queryKey: ['reception', 'list', params.toString()], queryFn: () => api<VisitPage>(`/api/v1/reception?${params}`), placeholderData: (p) => p, refetchInterval: 20_000 })
  const sum = useQuery({ queryKey: ['reception', 'summary'], queryFn: () => api<{ inside: number; expected_today: number; arrived_today: number }>('/api/v1/reception/summary'), enabled: viewer, refetchInterval: 20_000 })
  const act = useMutation({ mutationFn: ({ id, path }: { id: number; path: string }) => send('POST', `/api/v1/reception/${id}/${path}`, {}), onSuccess: () => void qc.invalidateQueries({ queryKey: ['reception'] }) })
  const reset = <T,>(fn: (v: T) => void) => (v: T) => (fn(v), setPage(1))

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <PageHeader
        title={t('reception.title')}
        subtitle={t('reception.subtitle')}
        actions={
          <Link to="/reception/new">
            <Button>
              <Plus className="size-4" />
              {t(desk ? 'reception.register' : 'reception.invite')}
            </Button>
          </Link>
        }
      />
      {sum.data && (
        <div className="grid grid-cols-3 gap-3">
          {(['inside', 'expected_today', 'arrived_today'] as const).map((k) => (
            <Card key={k} className="p-4">
              <div className="text-xs text-muted">{t(`reception.sum.${k}`)}</div>
              <div className="mt-1 text-2xl font-semibold tabular-nums">{sum.data[k]}</div>
            </Card>
          ))}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-3 rounded-card bg-surface p-3 shadow-card">
        {viewer && (
          <div className="flex rounded-control bg-(--seg-bg) p-0.5 text-[13px]" role="group">
            {(['all', 'mine'] as const).map((s) => (
              <button key={s} onClick={() => reset(setScope)(s)} aria-pressed={scope === s} className={scope === s ? 'rounded-lg bg-(--seg-on) px-3 py-1.5 font-medium text-text shadow-card' : 'rounded-lg px-3 py-1.5 text-muted transition-colors hover:text-text'}>
                {t(`reception.scope.${s}`)}
              </button>
            ))}
          </div>
        )}
        <Input className="w-52" value={text} onChange={(e) => reset(setText)(e.target.value)} placeholder={t('reception.search')} aria-label={t('reception.search')} />
        <Select className="w-auto" value={status} onChange={(e) => reset(setStatus)(e.target.value)} aria-label={t('attendance.statusLabel')}>
          <option value="">{t('attendance.allStatuses')}</option>
          <option value="open">{t('reception.openOnes')}</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {t(`reception.status.${s}`)}
            </option>
          ))}
        </Select>
        <Input type="date" className="w-40" value={date} onChange={(e) => reset(setDate)(e.target.value)} aria-label={t('reception.date')} />
      </div>
      {list.isLoading ? (
        <Skeleton className="h-48" />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border text-xs text-muted">
                <tr>
                  <th className="px-5 py-2.5 font-medium">{t('reception.visitor')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('attendance.statusLabel')}</th>
                  <th className="hidden px-5 py-2.5 font-medium md:table-cell">{t('reception.host')}</th>
                  <th className="hidden px-5 py-2.5 font-medium sm:table-cell">{t('reception.time')}</th>
                  {desk && <th className="px-5 py-2.5" />}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {list.data?.items.map((v) => (
                  <tr key={v.id}>
                    <td className="px-5 py-2.5">
                      <Link to={`/reception/${v.id}`} className="font-medium hover:text-primary hover:underline">
                        {v.visitor_name}
                      </Link>
                      <div className="mt-0.5 text-xs text-muted">
                        {t(`reception.purpose.${v.purpose}`)}
                        {v.company && ` · ${v.company}`}
                        {v.vehicle_plate && ` · ${v.vehicle_plate}`}
                        {v.badge_no && ` · #${v.badge_no}`}
                      </div>
                    </td>
                    <td className="px-5 py-2.5">
                      <Badge tone={STATUS_TONE[v.status]}>{t(`reception.status.${v.status}`)}</Badge>
                    </td>
                    <td className="hidden px-5 py-2.5 text-muted md:table-cell">{v.host?.name ?? '—'}</td>
                    <td className="hidden px-5 py-2.5 tabular-nums text-muted sm:table-cell">
                      {v.status === 'expected' || !v.arrived_at ? formatDateTime(v.expected_at, i18n.language) : formatDateTime(v.arrived_at, i18n.language)}
                    </td>
                    {desk && (
                      <td className="px-5 py-2.5 text-right">
                        {v.status === 'expected' && (
                          <Button variant="outline" className="h-8" disabled={act.isPending} onClick={() => act.mutate({ id: v.id, path: 'arrive' })}>
                            <LogIn className="size-4" />
                            {t('reception.arrive')}
                          </Button>
                        )}
                        {v.status === 'arrived' && (
                          <Button variant="outline" className="h-8" disabled={act.isPending} onClick={() => act.mutate({ id: v.id, path: 'leave' })}>
                            <LogOut className="size-4" />
                            {t('reception.leave')}
                          </Button>
                        )}
                      </td>
                    )}
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
      {act.isError && (
        <p role="alert" className="text-sm text-danger">
          {errorText(t, act.error)}
        </p>
      )}
      {list.data && list.data.total > SIZE && <Pagination page={page} size={SIZE} total={list.data.total} onPage={setPage} />}
    </div>
  )
}
