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
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { useCan } from '../auth/useAuth'
import { LogisticsTabs } from './LogisticsTabs'
import { num, type Vehicle } from './api'

/** /logistics/vehicles: mashinalar ro'yxati. */
export function VehiclesPage() {
  const { t } = useTranslation()
  const manage = useCan()('logistics.manage')
  const [text, setText] = useState('')
  const [status, setStatus] = useState('')
  const params = new URLSearchParams()
  if (text.trim()) params.set('q', text.trim())
  if (status) params.set('status', status)
  const q = useQuery({ queryKey: ['logistics', 'vehicles', params.toString()], queryFn: () => api<Vehicle[]>(`/api/v1/logistics/vehicles?${params}`), placeholderData: (p) => p })
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <PageHeader
        title={t('logistics.title')}
        subtitle={t('logistics.subtitle')}
        actions={
          manage && (
            <Link to="/logistics/vehicles/new">
              <Button>
                <Plus className="size-4" />
                {t('logistics.vehicle.add')}
              </Button>
            </Link>
          )
        }
      />
      <LogisticsTabs />
      <div className="flex flex-wrap items-center gap-3 rounded-card bg-surface p-3 shadow-card">
        <Input className="w-56" value={text} onChange={(e) => setText(e.target.value)} placeholder={t('logistics.vehicle.search')} aria-label={t('logistics.vehicle.search')} />
        <Select className="w-auto" value={status} onChange={(e) => setStatus(e.target.value)} aria-label={t('attendance.statusLabel')}>
          <option value="">{t('attendance.allStatuses')}</option>
          {(['active', 'service', 'retired'] as const).map((s) => (
            <option key={s} value={s}>
              {t(`logistics.vehicle.status.${s}`)}
            </option>
          ))}
        </Select>
      </div>
      {!q.data ? (
        <Skeleton className="h-48" />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {q.data.map((v) => (
            <Link key={v.id} to={`/logistics/vehicles/${v.id}`}>
              <Card className="flex h-full flex-col gap-2 p-5 transition-shadow hover:shadow-card">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="text-lg font-semibold tracking-wide">{v.plate}</div>
                    <div className="text-sm text-muted">{v.name}</div>
                  </div>
                  <Badge tone={v.status === 'active' ? 'success' : v.status === 'service' ? 'warning' : 'neutral'}>{t(`logistics.vehicle.status.${v.status}`)}</Badge>
                </div>
                <div className="text-xs text-muted tabular-nums">
                  {t(`logistics.fuelType.${v.fuel_type}`)} · {v.fuel_norm} l/100 km · {num(v.odometer_km)} km
                </div>
                <div className="mt-auto flex flex-wrap gap-1.5">
                  {v.active_trip_id && <Badge tone="warning">{t('logistics.vehicle.onTrip')}</Badge>}
                  {(v.docs?.expired ?? 0) > 0 && <Badge tone="danger">{t('logistics.vehicle.docsExpired', { count: v.docs?.expired })}</Badge>}
                  {(v.docs?.soon ?? 0) > 0 && <Badge tone="warning">{t('logistics.vehicle.docsSoon', { count: v.docs?.soon })}</Badge>}
                </div>
              </Card>
            </Link>
          ))}
          {q.data.length === 0 && <p className="col-span-full py-10 text-center text-muted">{t('common.empty')}</p>}
        </div>
      )}
    </div>
  )
}
