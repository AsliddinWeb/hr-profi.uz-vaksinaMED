import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input, Select } from '../../components/ui/Input'
import { Pagination } from '../../components/ui/Pagination'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { addDays, todayLocal } from '../attendance/api'
import { useCan } from '../auth/useAuth'
import { LogisticsTabs } from './LogisticsTabs'
import { num, type Fuel, type Page, type Vehicle } from './api'

const SIZE = 30

/** /logistics/fuel: yoqilg'i quyish yozuvlari. */
export function FuelPage() {
  const { t, i18n } = useTranslation()
  const manage = useCan()('logistics.manage')
  const [sp] = useSearchParams()
  const [vehicle, setVehicle] = useState(sp.get('vehicle_id') ?? '')
  const today = todayLocal()
  const [range, setRange] = useState({ start: addDays(today, -29), end: today })
  const [page, setPage] = useState(1)
  const params = new URLSearchParams({ ...range, page: String(page), size: String(SIZE) })
  if (vehicle) params.set('vehicle_id', vehicle)
  const q = useQuery({ queryKey: ['logistics', 'fuel', params.toString()], queryFn: () => api<Page<Fuel>>(`/api/v1/logistics/fuel?${params}`), placeholderData: (p) => p })
  const vehicles = useQuery({ queryKey: ['logistics', 'vehicles', ''], queryFn: () => api<Vehicle[]>('/api/v1/logistics/vehicles') })
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <PageHeader
        title={t('logistics.title')}
        subtitle={t('logistics.subtitle')}
        actions={
          manage && (
            <Link to="/logistics/fuel/new">
              <Button>
                <Plus className="size-4" />
                {t('logistics.fuel.add')}
              </Button>
            </Link>
          )
        }
      />
      <LogisticsTabs />
      <div className="flex flex-wrap items-center gap-3 rounded-card bg-surface p-3 shadow-card">
        <Select className="w-auto" value={vehicle} onChange={(e) => (setVehicle(e.target.value), setPage(1))} aria-label={t('logistics.trip.vehicle')}>
          <option value="">{t('logistics.fuel.allVehicles')}</option>
          {vehicles.data?.map((v) => (
            <option key={v.id} value={v.id}>
              {v.plate}
            </option>
          ))}
        </Select>
        <Input type="date" className="w-40" value={range.start} max={range.end} onChange={(e) => e.target.value && (setRange({ ...range, start: e.target.value }), setPage(1))} aria-label={t('schedule.apply.from')} />
        <span className="text-muted">–</span>
        <Input type="date" className="w-40" value={range.end} min={range.start} onChange={(e) => e.target.value && (setRange({ ...range, end: e.target.value }), setPage(1))} aria-label={t('schedule.apply.to')} />
      </div>
      {!q.data ? (
        <Skeleton className="h-48" />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border text-xs text-muted">
                <tr>
                  <th className="px-5 py-2.5 font-medium">{t('logistics.fuel.when')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('logistics.trip.vehicle')}</th>
                  <th className="px-5 py-2.5 text-right font-medium">{t('logistics.fuel.liters')}</th>
                  <th className="hidden px-5 py-2.5 text-right font-medium sm:table-cell">{t('logistics.fuel.total')}</th>
                  <th className="hidden px-5 py-2.5 text-right font-medium md:table-cell">km</th>
                  <th className="hidden px-5 py-2.5 font-medium md:table-cell">{t('logistics.trip.driver')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border tabular-nums">
                {q.data.items.map((f) => (
                  <tr key={f.id}>
                    <td className="px-5 py-2.5">
                      {manage ? (
                        <Link to={`/logistics/fuel/${f.id}/edit`} className="hover:text-primary hover:underline">
                          {formatDateTime(f.fueled_at, i18n.language)}
                        </Link>
                      ) : (
                        formatDateTime(f.fueled_at, i18n.language)
                      )}
                      {f.station && <div className="text-xs text-muted">{f.station}</div>}
                    </td>
                    <td className="px-5 py-2.5 font-medium">{f.vehicle.plate}</td>
                    <td className="px-5 py-2.5 text-right">
                      {num(f.liters, 2)} {!f.full_tank && <Badge>{t('logistics.fuel.partial')}</Badge>}
                    </td>
                    <td className="hidden px-5 py-2.5 text-right sm:table-cell">{num(f.total)}</td>
                    <td className="hidden px-5 py-2.5 text-right text-muted md:table-cell">{num(f.odometer_km)}</td>
                    <td className="hidden px-5 py-2.5 text-muted md:table-cell">{f.driver?.name ?? '—'}</td>
                  </tr>
                ))}
                {q.data.items.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-5 py-10 text-center text-muted">
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
