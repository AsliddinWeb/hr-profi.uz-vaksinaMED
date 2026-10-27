import { useQuery } from '@tanstack/react-query'
import { lazy, Suspense, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDateTime, relativeTime } from '../../lib/format'
import { Kpi } from '../tasks/AnalyticsPage'
import { LogisticsTabs } from './LogisticsTabs'
import type { Live, Vehicle } from './api'

const BranchMap = lazy(() => import('../../components/map/BranchMap').then((m) => ({ default: m.BranchMap })))

/** /logistics: jonli xarita (faol reyslar, har 10 soniyada yangilanadi). */
export function LivePage() {
  const { t, i18n } = useTranslation()
  const [fit, setFit] = useState(true)
  const live = useQuery({ queryKey: ['logistics', 'live'], queryFn: () => api<Live[]>('/api/v1/logistics/live'), refetchInterval: 10_000 })
  const vehicles = useQuery({ queryKey: ['logistics', 'vehicles'], queryFn: () => api<Vehicle[]>('/api/v1/logistics/vehicles') })
  const points = useMemo(
    () =>
      (live.data ?? [])
        .filter((l) => l.lat !== null && l.lng !== null)
        .map((l) => ({ id: l.trip_id, lat: l.lat as number, lng: l.lng as number, label: l.vehicle.plate, popup: `${l.vehicle.plate} · ${l.driver.name ?? ''}${l.speed !== null ? ` · ${Math.round(l.speed)} km/h` : ''}`, color: l.stale ? '#9ca3af' : '#16a34a' })),
    [live.data],
  )
  const docs = (vehicles.data ?? []).reduce((a, v) => ({ expired: a.expired + (v.docs?.expired ?? 0), soon: a.soon + (v.docs?.soon ?? 0) }), { expired: 0, soon: 0 })
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <PageHeader title={t('logistics.title')} subtitle={t('logistics.subtitle')} />
      <LogisticsTabs />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Kpi tint="mint" label={t('logistics.live.onRoad')} value={String(live.data?.length ?? 0)} />
        <Kpi label={t('logistics.live.vehicles')} value={String(vehicles.data?.length ?? 0)} />
        <Kpi tint="rose" label={t('logistics.live.expired')} value={String(docs.expired)} />
        <Kpi tint="sand" label={t('logistics.live.soon')} value={String(docs.soon)} />
      </div>
      <Suspense fallback={<Skeleton className="h-[420px]" />}>
        <BranchMap points={points} fit={fit} onSelect={() => setFit(false)} height={460} />
      </Suspense>
      <Card className="divide-y divide-border p-0">
        {live.data?.map((l) => (
          <Link key={l.trip_id} to={`/logistics/trips/${l.trip_id}`} className="flex flex-wrap items-center justify-between gap-3 px-5 py-2.5 hover:bg-surface-2">
            <div>
              <div className="font-medium">
                {l.vehicle.plate} <span className="text-sm font-normal text-muted">{l.vehicle.name}</span>
              </div>
              <div className="text-xs text-muted">
                {l.driver.name} · {l.purpose}
              </div>
            </div>
            <div className="text-right text-xs tabular-nums text-muted">
              {l.at ? (
                <>
                  {l.stale ? <Badge tone="warning">{t('logistics.live.stale')}</Badge> : <Badge tone="success">{l.speed !== null ? `${Math.round(l.speed)} km/h` : 'GPS'}</Badge>}
                  <div className="mt-1" title={formatDateTime(l.at, i18n.language)}>
                    {relativeTime(l.at, i18n.language)}
                  </div>
                </>
              ) : (
                <Badge>{t('logistics.live.noSignal')}</Badge>
              )}
            </div>
          </Link>
        ))}
        {live.data?.length === 0 && <p className="px-5 py-8 text-center text-sm text-muted">{t('logistics.live.none')}</p>}
      </Card>
    </div>
  )
}
