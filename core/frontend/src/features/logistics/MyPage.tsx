import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Fuel, MapPin, Play, Square } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { api, send } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { errorText } from '../auth/errorText'
import { useGpsTracking } from './useGpsTracking'
import { num, type Trip } from './api'

interface My {
  employee: { id: number; name: string } | null
  active: Trip | null
  planned: Trip[]
}

/** /logistics/my: haydovchi sahifasi (telefon): faol reys, GPS kuzatuv, boshlash/yakunlash va yoqilg'i. */
export function MyPage() {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['logistics', 'my'], queryFn: () => api<My>('/api/v1/logistics/my'), refetchInterval: 30_000 })
  const [odo, setOdo] = useState('')
  const [note, setNote] = useState('')
  const gps = useGpsTracking(!!q.data?.active)
  const act = useMutation({
    mutationFn: ({ id, path, body }: { id: number; path: string; body: unknown }) => send('POST', `/api/v1/logistics/trips/${id}/${path}`, body),
    onSuccess: () => {
      setOdo('')
      setNote('')
      void qc.invalidateQueries({ queryKey: ['logistics'] })
    },
  })
  if (!q.data) return <Skeleton className="mx-auto h-96 max-w-xl" />
  const { active, planned } = q.data
  return (
    <div className="mx-auto flex max-w-xl flex-col gap-4">
      <PageHeader title={t('logistics.my.title')} subtitle={q.data.employee?.name ?? t('logistics.my.noEmployee')} />
      {active ? (
        <Card tint="mint" className="flex flex-col gap-4 p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <Link to={`/logistics/trips/${active.id}`} className="text-lg font-semibold hover:underline">
                {active.purpose}
              </Link>
              <div className="text-sm text-muted">
                {active.vehicle.plate} · {active.vehicle.name}
              </div>
            </div>
            <Badge tone="warning">{t('logistics.trip.status.active')}</Badge>
          </div>
          <div className="rounded-control bg-surface p-3 text-sm">
            <div className="flex items-center gap-2 font-medium">
              <MapPin className="size-4" />
              {t(`logistics.my.gps.${gps.state}`)}
            </div>
            <div className="mt-1 text-xs text-muted tabular-nums">
              {gps.last ? `${gps.last.lat.toFixed(5)}, ${gps.last.lng.toFixed(5)} · ±${Math.round(gps.last.accuracy ?? 0)} m · ` : ''}
              {t('logistics.my.sent', { sent: gps.sent, queued: gps.queued })}
            </div>
            {gps.state === 'denied' && <p className="mt-1 text-xs text-danger">{t('logistics.my.gpsDenied')}</p>}
          </div>
          <div className="flex flex-col gap-2">
            <Input type="number" min={active.start_odometer ?? 0} value={odo} onChange={(e) => setOdo(e.target.value)} placeholder={`${t('logistics.trip.odometerNow')} (≥ ${num(active.start_odometer)})`} aria-label={t('logistics.trip.odometerNow')} />
            <Input value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} placeholder={t('recruit.candidate.note')} aria-label={t('recruit.candidate.note')} />
            <div className="flex gap-2">
              <Button className="flex-1" disabled={act.isPending || odo === ''} onClick={() => act.mutate({ id: active.id, path: 'finish', body: { odometer: Number(odo), note: note || null } })}>
                <Square className="size-4" />
                {t('logistics.trip.finish')}
              </Button>
              <Link to={`/logistics/fuel/new?trip_id=${active.id}`}>
                <Button variant="outline">
                  <Fuel className="size-4" />
                  {t('logistics.fuel.add')}
                </Button>
              </Link>
            </div>
          </div>
        </Card>
      ) : (
        <p className="rounded-card bg-surface p-5 text-center text-sm text-muted shadow-card">{t('logistics.my.noActive')}</p>
      )}
      {planned.map((p) => (
        <Card key={p.id} className="flex flex-col gap-3 p-5">
          <div>
            <Link to={`/logistics/trips/${p.id}`} className="font-semibold hover:underline">
              {p.purpose}
            </Link>
            <div className="text-sm text-muted">
              {p.vehicle.plate} · {p.vehicle.name} · {formatDateTime(p.planned_start, i18n.language)}
            </div>
            {(p.origin || p.destination) && (
              <div className="text-xs text-muted">
                {p.origin} → {p.destination}
              </div>
            )}
          </div>
          {!active && (
            <div className="flex gap-2">
              <Input type="number" min={p.vehicle.odometer_km ?? 0} value={odo} onChange={(e) => setOdo(e.target.value)} placeholder={`${t('logistics.trip.odometerNow')} (≥ ${num(p.vehicle.odometer_km)})`} aria-label={t('logistics.trip.odometerNow')} />
              <Button disabled={act.isPending || odo === ''} onClick={() => act.mutate({ id: p.id, path: 'start', body: { odometer: Number(odo) } })}>
                <Play className="size-4" />
                {t('logistics.trip.start')}
              </Button>
            </div>
          )}
        </Card>
      ))}
      {act.isError && (
        <p role="alert" className="text-sm text-danger">
          {errorText(t, act.error)}
        </p>
      )}
    </div>
  )
}
