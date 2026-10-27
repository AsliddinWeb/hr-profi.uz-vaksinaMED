import { useQuery } from '@tanstack/react-query'
import { CalendarClock, Plus, Search } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input, Select } from '../../components/ui/Input'
import { Pagination } from '../../components/ui/Pagination'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { useCan } from '../auth/useAuth'
import { PenaltyList } from './PenaltyList'
import { money, PSTATUSES, TYPES, type PenaltyPage } from './api'

const SIZE = 30
type Scope = 'mine' | 'all'

/** /penalties: jarimalar (mening / hammasi), holat va tur bo'yicha filtr. */
export function PenaltiesPage() {
  const { t } = useTranslation()
  const can = useCan()
  const all = can('penalties.read') || can('penalties.approve') || can('penalties.manage')
  const [scope, setScope] = useState<Scope>(all ? 'all' : 'mine')
  const [status, setStatus] = useState(all ? 'pending' : '')
  const [type, setType] = useState('')
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const params = new URLSearchParams({ scope, page: String(page), size: String(SIZE) })
  if (status) params.set('status', status)
  if (type) params.set('incident_type', type)
  if (q.trim()) params.set('q', q.trim())
  const list = useQuery({ queryKey: ['penalties', 'list', params.toString()], queryFn: () => api<PenaltyPage>(`/api/v1/penalties?${params}`), placeholderData: (p) => p, refetchInterval: 60_000 })

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader
        title={t('penalties.title')}
        subtitle={t('penalties.subtitle')}
        actions={
          can('penalties.manage') && (
            <>
              <Link to="/penalties/scan">
                <Button variant="outline">
                  <CalendarClock className="size-4" />
                  {t('penalties.scan.title')}
                </Button>
              </Link>
              <Link to="/penalties/new">
                <Button>
                  <Plus className="size-4" />
                  {t('penalties.add')}
                </Button>
              </Link>
            </>
          )
        }
      />
      <Card className="flex flex-wrap items-center gap-3 p-4">
        {all && (
          <div className="flex rounded-control bg-(--seg-bg) p-0.5 text-[13px]">
            {(['all', 'mine'] as const).map((s) => (
              <button key={s} onClick={() => (setScope(s), setPage(1))} className={scope === s ? 'rounded-lg bg-(--seg-on) px-3 py-1.5 font-medium text-text shadow-card' : 'rounded-lg px-3 py-1.5 text-muted transition-colors hover:text-text'}>
                {t(`penalties.scope.${s}`)}
              </button>
            ))}
          </div>
        )}
        {scope === 'all' && (
          <label className="relative min-w-36 max-w-64 flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
            <Input className="pl-9" placeholder={t('schedule.searchEmployee')} value={q} onChange={(e) => (setQ(e.target.value), setPage(1))} aria-label={t('schedule.searchEmployee')} />
          </label>
        )}
        <Select className="w-auto" value={status} onChange={(e) => (setStatus(e.target.value), setPage(1))} aria-label={t('attendance.statusLabel')}>
          <option value="">{t('attendance.allStatuses')}</option>
          {PSTATUSES.map((s) => (
            <option key={s} value={s}>
              {t(`penalties.status.${s}`)}
            </option>
          ))}
        </Select>
        <Select className="w-auto" value={type} onChange={(e) => (setType(e.target.value), setPage(1))} aria-label={t('penalties.violation')}>
          <option value="">{t('penalties.allTypes')}</option>
          {TYPES.map((k) => (
            <option key={k} value={k}>
              {t(`letters.incidents.${k}`)}
            </option>
          ))}
        </Select>
      </Card>
      {list.data && (
        <p className="text-sm text-muted">
          {t('penalties.approvedSum')}: <b className="tabular-nums text-text">{money(list.data.approved_amount)}</b>
        </p>
      )}
      {list.isLoading ? <Skeleton className="h-40" /> : <PenaltyList items={list.data?.items ?? []} showEmployee={scope === 'all'} empty={t('common.empty')} />}
      {list.data && list.data.total > SIZE && <Pagination page={page} size={SIZE} total={list.data.total} onPage={setPage} />}
    </div>
  )
}
