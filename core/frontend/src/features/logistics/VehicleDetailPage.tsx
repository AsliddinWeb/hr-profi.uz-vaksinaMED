import { useQuery } from '@tanstack/react-query'
import { Pencil, Plus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Info } from '../../components/ui/Info'
import { Skeleton } from '../../components/ui/Skeleton'
import { api, ApiError } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { useCan } from '../auth/useAuth'
import { num, stageTone, TSTATUS_TONE, type Doc, type Page, type Trip, type Vehicle } from './api'

/** /logistics/vehicles/:id: mashina kartasi, hujjatlar va oxirgi reyslar. */
export function VehicleDetailPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const manage = useCan()('logistics.manage')
  const q = useQuery({ queryKey: ['logistics', 'vehicle', id], queryFn: () => api<Vehicle>(`/api/v1/logistics/vehicles/${id}`), retry: false })
  const docs = useQuery({ queryKey: ['logistics', 'docs', id], queryFn: () => api<Doc[]>(`/api/v1/logistics/vehicles/${id}/documents`) })
  const trips = useQuery({ queryKey: ['logistics', 'trips', 'vehicle', id], queryFn: () => api<Page<Trip>>(`/api/v1/logistics/trips?vehicle_id=${id}&size=8`) })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const v = q.data
  if (!v) return <Skeleton className="mx-auto h-96 max-w-4xl" />
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title={v.plate}
        subtitle={v.name}
        backTo="/logistics/vehicles"
        backLabel={t('logistics.tabs.vehicles')}
        actions={
          manage && (
            <Link to={`/logistics/vehicles/${id}/edit`}>
              <Button variant="outline">
                <Pencil className="size-4" />
                {t('common.edit')}
              </Button>
            </Link>
          )
        }
      />
      <Card className="grid gap-4 p-6 text-sm sm:grid-cols-4">
        <Info label={t('logistics.vehicle.statusLabel')}>{t(`logistics.vehicle.status.${v.status}`)}</Info>
        <Info label={t('logistics.vehicle.fuelType')}>{t(`logistics.fuelType.${v.fuel_type}`)}</Info>
        <Info label={t('logistics.vehicle.norm')}>{v.fuel_norm} l/100 km</Info>
        <Info label={t('logistics.vehicle.odometer')}>{num(v.odometer_km)} km</Info>
        <Info label={t('logistics.vehicle.branch')}>{v.branch?.name ?? '—'}</Info>
        <Info label={t('logistics.vehicle.tank')}>{v.tank_l ? `${v.tank_l} l` : '—'}</Info>
        {v.note && <p className="text-muted sm:col-span-4">{v.note}</p>}
      </Card>
      <Card className="p-6">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-[15px] font-medium">{t('logistics.doc.title')}</h2>
          {manage && (
            <Link to={`/logistics/vehicles/${id}/documents/new`}>
              <Button variant="outline">
                <Plus className="size-4" />
                {t('logistics.doc.add')}
              </Button>
            </Link>
          )}
        </div>
        <ul className="mt-3 divide-y divide-border text-sm">
          {docs.data?.map((d) => (
            <li key={d.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
              <span>
                {manage ? (
                  <Link to={`/logistics/documents/${d.id}/edit`} className="font-medium hover:text-primary hover:underline">
                    {t(`logistics.docKind.${d.kind}`)}
                  </Link>
                ) : (
                  <span className="font-medium">{t(`logistics.docKind.${d.kind}`)}</span>
                )}
                {d.number && <span className="ml-2 text-muted">{d.number}</span>}
              </span>
              <span className="flex items-center gap-2 tabular-nums">
                {formatDate(d.expires_at, i18n.language)}
                <Badge tone={stageTone(d.stage)}>{d.days_left < 0 ? t('logistics.doc.expired', { days: -d.days_left }) : t('logistics.doc.daysLeft', { days: d.days_left })}</Badge>
              </span>
            </li>
          ))}
          {docs.data?.length === 0 && <li className="py-6 text-center text-muted">{t('common.empty')}</li>}
        </ul>
      </Card>
      <Card className="p-6">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-[15px] font-medium">{t('logistics.trip.recent')}</h2>
          <Link to={`/logistics/fuel?vehicle_id=${id}`} className="text-sm text-primary hover:underline">
            {t('logistics.tabs.fuel')}
          </Link>
        </div>
        <ul className="mt-3 divide-y divide-border text-sm">
          {trips.data?.items.map((x) => (
            <li key={x.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
              <Link to={`/logistics/trips/${x.id}`} className="font-medium hover:text-primary hover:underline">
                {x.purpose}
              </Link>
              <span className="flex items-center gap-2 text-muted">
                {x.driver.name}
                {x.distance_km !== null && <span className="tabular-nums">{num(x.distance_km, 1)} km</span>}
                <Badge tone={TSTATUS_TONE[x.status]}>{t(`logistics.trip.status.${x.status}`)}</Badge>
              </span>
            </li>
          ))}
          {trips.data?.items.length === 0 && <li className="py-6 text-center text-muted">{t('common.empty')}</li>}
        </ul>
      </Card>
    </div>
  )
}
