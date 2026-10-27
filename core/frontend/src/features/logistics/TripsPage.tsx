import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
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
import { formatDateTime } from '../../lib/format'
import { useCan } from '../auth/useAuth'
import { LogisticsTabs } from './LogisticsTabs'
import { num, TSTATUS_TONE, type Page, type Trip } from './api'

const SIZE = 25

/** /logistics/trips: reyslar ro'yxati. */
export function TripsPage() {
  const { t, i18n } = useTranslation()
  const manage = useCan()('logistics.manage')
  const [status, setStatus] = useState('open')
  const [page, setPage] = useState(1)
  const params = new URLSearchParams({ page: String(page), size: String(SIZE) })
  if (status) params.set('status', status)
  const q = useQuery({ queryKey: ['logistics', 'trips', params.toString()], queryFn: () => api<Page<Trip>>(`/api/v1/logistics/trips?${params}`), placeholderData: (p) => p })
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <PageHeader
        title={t('logistics.title')}
        subtitle={t('logistics.subtitle')}
        actions={
          manage && (
            <Link to="/logistics/trips/new">
              <Button>
                <Plus className="size-4" />
                {t('logistics.trip.add')}
              </Button>
            </Link>
          )
        }
      />
      <LogisticsTabs />
      <div className="flex flex-wrap items-center gap-3 rounded-card bg-surface p-3 shadow-card">
        <Select className="w-auto" value={status} onChange={(e) => (setStatus(e.target.value), setPage(1))} aria-label={t('attendance.statusLabel')}>
          <option value="open">{t('logistics.trip.openOnes')}</option>
          <option value="">{t('attendance.allStatuses')}</option>
          {(['planned', 'active', 'completed', 'cancelled'] as const).map((s) => (
            <option key={s} value={s}>
              {t(`logistics.trip.status.${s}`)}
            </option>
          ))}
        </Select>
      </div>
      {!q.data ? (
        <Skeleton className="h-48" />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border text-xs text-muted">
                <tr>
                  <th className="px-5 py-2.5 font-medium">{t('logistics.trip.purpose')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('logistics.trip.vehicle')}</th>
                  <th className="hidden px-5 py-2.5 font-medium md:table-cell">{t('logistics.trip.driver')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('attendance.statusLabel')}</th>
                  <th className="hidden px-5 py-2.5 text-right font-medium sm:table-cell">km</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border tabular-nums">
                {q.data.items.map((x) => (
                  <tr key={x.id}>
                    <td className="px-5 py-2.5">
                      <Link to={`/logistics/trips/${x.id}`} className="font-medium hover:text-primary hover:underline">
                        {x.purpose}
                      </Link>
                      <div className="text-xs text-muted">{formatDateTime(x.started_at ?? x.planned_start, i18n.language)}</div>
                    </td>
                    <td className="px-5 py-2.5">{x.vehicle.plate}</td>
                    <td className="hidden px-5 py-2.5 text-muted md:table-cell">{x.driver.name}</td>
                    <td className="px-5 py-2.5">
                      <Badge tone={TSTATUS_TONE[x.status]}>{t(`logistics.trip.status.${x.status}`)}</Badge>
                    </td>
                    <td className="hidden px-5 py-2.5 text-right sm:table-cell">{num(x.distance_km, 1)}</td>
                  </tr>
                ))}
                {q.data.items.length === 0 && (
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
      {q.data && q.data.total > SIZE && <Pagination page={page} size={SIZE} total={q.data.total} onPage={setPage} />}
    </div>
  )
}
