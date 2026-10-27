import { useQuery } from '@tanstack/react-query'
import { BatteryLow, BatteryMedium } from 'lucide-react'
import { lazy, Suspense, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { relativeTime } from '../../lib/format'
import { Kpi } from '../tasks/AnalyticsPage'
import { MobileTabs } from './MobileTabs'
import type { Ev, Live, Page } from './api'

const BranchMap = lazy(() => import('../../components/map/BranchMap').then((m) => ({ default: m.BranchMap })))

/** /mobile: jonli xarita: ish kunida bo'lgan ko'chma xodimlar (10 soniyada yangilanadi). */
export function LivePage() {
  const { t, i18n } = useTranslation()
  const live = useQuery({ queryKey: ['mobile', 'live'], queryFn: () => api<Live[]>('/api/v1/mobile/live'), refetchInterval: 10_000 })
  const open = useQuery({ queryKey: ['mobile', 'events', 'open'], queryFn: () => api<Page<Ev>>('/api/v1/mobile/events?open_only=true&size=1'), refetchInterval: 30_000 })
  const points = useMemo(
    () => (live.data ?? []).filter((l) => l.lat !== null && l.lng !== null).map((l) => ({ id: l.session_id, lat: l.lat as number, lng: l.lng as number, label: l.employee.name ?? '', popup: `${l.employee.name} · ${l.battery ?? '?'}%`, color: l.open_events > 0 ? '#dc2626' : l.stale ? '#9ca3af' : '#16a34a' })),
    [live.data],
  )
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <PageHeader title={t('mobile.title')} subtitle={t('mobile.subtitle')} />
      <MobileTabs />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
        <Kpi tint="mint" label={t('mobile.live.active')} value={String(live.data?.length ?? 0)} />
        <Kpi tint={(open.data?.total ?? 0) > 0 ? 'rose' : undefined} label={t('mobile.live.openEvents')} value={String(open.data?.total ?? 0)} hint={(open.data?.total ?? 0) > 0 ? undefined : t('mobile.live.allClear')} />
        <Kpi tint="sand" label={t('mobile.live.stale')} value={String((live.data ?? []).filter((l) => l.stale).length)} />
      </div>
      <Suspense fallback={<Skeleton className="h-[420px]" />}>
        <BranchMap points={points} height={440} />
      </Suspense>
      <Card className="divide-y divide-border p-0">
        {live.data?.map((l) => (
          <Link key={l.session_id} to={`/mobile/sessions/${l.session_id}`} className="flex flex-wrap items-center justify-between gap-3 px-5 py-2.5 hover:bg-surface-2">
            <div>
              <div className="font-medium">{l.employee.name}</div>
              <div className="text-xs tabular-nums text-muted">
                {l.distance_km.toFixed(1)} km · {relativeTime(l.at, i18n.language)}
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              {l.open_events > 0 && <Badge tone="danger">{t('mobile.live.events', { count: l.open_events })}</Badge>}
              {l.stale && <Badge tone="warning">{t('mobile.live.noSignal')}</Badge>}
              {l.gps_off && <Badge tone="warning">GPS off</Badge>}
              {l.permission && l.permission !== 'granted' && <Badge tone="danger">{t('mobile.live.noPermission')}</Badge>}
              <span className={'inline-flex items-center gap-1 tabular-nums ' + ((l.battery ?? 100) <= 15 ? 'text-danger' : 'text-muted')}>
                {(l.battery ?? 100) <= 15 ? <BatteryLow className="size-4" /> : <BatteryMedium className="size-4" />}
                {l.battery === null ? '?' : `${l.battery}%`}
              </span>
            </div>
          </Link>
        ))}
        {live.data?.length === 0 && <p className="px-5 py-8 text-center text-sm text-muted">{t('mobile.live.none')}</p>}
      </Card>
    </div>
  )
}
