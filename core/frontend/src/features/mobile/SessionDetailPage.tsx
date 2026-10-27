import { useQuery } from '@tanstack/react-query'
import { lazy, Suspense } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api, ApiError } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { SEV_TONE, type Ev, type Session } from './api'

const BranchMap = lazy(() => import('../../components/map/BranchMap').then((m) => ({ default: m.BranchMap })))

/** /mobile/sessions/:id: sessiya, trek xaritasi va hodisalar. Trekni ko'rish auditga yoziladi. */
export function SessionDetailPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const q = useQuery({ queryKey: ['mobile', 'session', id], queryFn: () => api<Session & { events: Ev[] }>(`/api/v1/mobile/sessions/${id}`), retry: false, refetchInterval: 20_000 })
  const track = useQuery({ queryKey: ['mobile', 'track', id], queryFn: () => api<{ total: number; points: { lat: number; lng: number }[] }>(`/api/v1/mobile/sessions/${id}/track`), enabled: !!q.data })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const s = q.data
  if (!s) return <Skeleton className="mx-auto h-96 max-w-4xl" />
  const path = track.data?.points ?? []
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader title={s.employee?.name ?? '—'} subtitle={formatDateTime(s.started_at, i18n.language)} backTo="/mobile/sessions" backLabel={t('mobile.tabs.sessions')} actions={<Badge tone={s.status === 'active' ? 'warning' : 'success'}>{t(`mobile.session.status.${s.status}`)}</Badge>} />
      <Card className="grid gap-4 p-6 text-sm sm:grid-cols-4">
        <Info label={t('mobile.session.started')}>{formatDateTime(s.started_at, i18n.language)}</Info>
        <Info label={t('mobile.session.ended')}>{s.ended_at ? `${formatDateTime(s.ended_at, i18n.language)}${s.end_reason ? ` · ${t(`mobile.session.reason.${s.end_reason}`)}` : ''}` : '—'}</Info>
        <Info label="km">{s.distance_km.toFixed(2)}</Info>
        <Info label={t('mobile.session.points')}>{s.points_count}</Info>
      </Card>
      <p className="text-xs text-muted">{t('mobile.session.auditNote')}</p>
      {path.length > 1 && (
        <Suspense fallback={<Skeleton className="h-96" />}>
          <BranchMap path={path} height={400} />
        </Suspense>
      )}
      <Card className="p-6">
        <h2 className="font-semibold">{t('mobile.tabs.events')}</h2>
        <ul className="mt-3 divide-y divide-border text-sm">
          {s.events.map((e) => (
            <li key={e.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
              <span className="flex items-center gap-2">
                <Badge tone={SEV_TONE[e.severity]}>{t(`mobile.event.${e.kind}`)}</Badge>
                {e.acknowledged_at && <span className="text-xs text-muted">{t('mobile.event.ack')}</span>}
              </span>
              <span className="text-xs text-muted tabular-nums">{formatDateTime(e.created_at, i18n.language)}</span>
            </li>
          ))}
          {s.events.length === 0 && <li className="py-6 text-center text-muted">{t('common.empty')}</li>}
        </ul>
      </Card>
    </div>
  )
}

function Info({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="mt-1 tabular-nums">{children}</dd>
    </div>
  )
}
