import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Pencil, Play, Square } from 'lucide-react'
import { lazy, Suspense, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Info } from '../../components/ui/Info'
import { Input } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { api, ApiError, send } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { num, TSTATUS_TONE, type TripDetail } from './api'

const BranchMap = lazy(() => import('../../components/map/BranchMap').then((m) => ({ default: m.BranchMap })))
const area = 'w-full rounded-control border border-border bg-surface px-3 py-2 text-sm'

/** /logistics/trips/:id: reys, GPS trek xaritasi va amallar (boshlash, yakunlash, bekor qilish). */
export function TripDetailPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const qc = useQueryClient()
  const confirm = useConfirm()
  const [odo, setOdo] = useState('')
  const [note, setNote] = useState('')
  const [reason, setReason] = useState('')
  const q = useQuery({ queryKey: ['logistics', 'trip', id], queryFn: () => api<TripDetail>(`/api/v1/logistics/trips/${id}`), retry: false, refetchInterval: 20_000 })
  const track = useQuery({ queryKey: ['logistics', 'track', id], queryFn: () => api<{ points: { lat: number; lng: number }[] }>(`/api/v1/logistics/trips/${id}/track`), enabled: !!q.data && q.data.points > 0 })
  const act = useMutation({ mutationFn: ({ path, body }: { path: string; body: unknown }) => send('POST', `/api/v1/logistics/trips/${id}/${path}`, body), onSuccess: () => void qc.invalidateQueries({ queryKey: ['logistics'] }) })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const tr = q.data
  if (!tr) return <Skeleton className="mx-auto h-96 max-w-4xl" />
  const path = track.data?.points ?? []
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title={tr.purpose}
        subtitle={`${tr.vehicle.plate} · ${tr.driver.name ?? ''}`}
        backTo={tr.can.mine && !tr.can.cancel ? '/logistics/my' : '/logistics/trips'}
        backLabel={t('logistics.tabs.trips')}
        actions={
          <>
            <Badge tone={TSTATUS_TONE[tr.status]}>{t(`logistics.trip.status.${tr.status}`)}</Badge>
            {tr.can.edit && (
              <Link to={`/logistics/trips/${id}/edit`}>
                <Button variant="outline">
                  <Pencil className="size-4" />
                  {t('common.edit')}
                </Button>
              </Link>
            )}
          </>
        }
      />
      <Card className="grid gap-4 p-6 text-sm sm:grid-cols-4">
        <Info label={t('logistics.trip.origin')}>{tr.origin ?? '—'}</Info>
        <Info label={t('logistics.trip.destination')}>{tr.destination ?? '—'}</Info>
        <Info label={t('logistics.trip.started')}>{formatDateTime(tr.started_at ?? tr.planned_start, i18n.language)}</Info>
        <Info label={t('logistics.trip.finished')}>{formatDateTime(tr.finished_at, i18n.language)}</Info>
        <Info label={t('logistics.trip.odometer')}>
          {num(tr.start_odometer)} → {num(tr.end_odometer)}
        </Info>
        <Info label={t('logistics.trip.distance')}>{num(tr.distance_km, 1)} km</Info>
        <Info label={t('logistics.trip.gpsKm')}>{num(tr.gps_km, 1)} km</Info>
        <Info label={t('logistics.trip.normL')}>{num(tr.fuel_norm_l, 2)} l</Info>
        {tr.note && <p className="text-muted sm:col-span-4">{tr.note}</p>}
      </Card>
      {path.length > 1 && (
        <Suspense fallback={<Skeleton className="h-96" />}>
          <BranchMap path={path} height={380} />
        </Suspense>
      )}
      {(tr.can.start || tr.can.finish || tr.can.cancel) && (
        <Card className="flex flex-col gap-5 p-6">
          {tr.can.start && (
            <section className="flex flex-col gap-3" aria-labelledby="trip-start">
              <h2 id="trip-start" className="text-[15px] font-medium">{t('logistics.trip.startTitle')}</h2>
              <Input type="number" min={0} value={odo} onChange={(e) => setOdo(e.target.value)} placeholder={t('logistics.trip.odometerNow')} aria-label={t('logistics.trip.odometerNow')} className="max-w-xs" />
              <div>
                <Button disabled={act.isPending || odo === ''} onClick={() => act.mutate({ path: 'start', body: { odometer: Number(odo) } })}>
                  <Play className="size-4" />
                  {t('logistics.trip.start')}
                </Button>
              </div>
            </section>
          )}
          {tr.can.finish && (
            <section className="flex flex-col gap-3" aria-labelledby="trip-finish">
              <h2 id="trip-finish" className="text-[15px] font-medium">{t('logistics.trip.finishTitle')}</h2>
              <Input type="number" min={tr.start_odometer ?? 0} value={odo} onChange={(e) => setOdo(e.target.value)} placeholder={t('logistics.trip.odometerNow')} aria-label={t('logistics.trip.odometerNow')} className="max-w-xs" />
              <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={2000} placeholder={t('recruit.candidate.note')} aria-label={t('recruit.candidate.note')} className={area} />
              <div>
                <Button disabled={act.isPending || odo === ''} onClick={() => act.mutate({ path: 'finish', body: { odometer: Number(odo), note: note || null } })}>
                  <Square className="size-4" />
                  {t('logistics.trip.finish')}
                </Button>
              </div>
            </section>
          )}
          {tr.can.cancel && (
            <section className="flex flex-col gap-2 border-t border-border pt-4 first:border-0 first:pt-0" aria-labelledby="trip-cancel">
              <h2 id="trip-cancel" className="text-sm font-medium">{t('logistics.trip.cancelTitle')}</h2>
              <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} maxLength={500} placeholder={t('logistics.trip.cancelHint')} aria-label={t('logistics.trip.cancelTitle')} className={area} />
              <div>
                <Button
                  variant="outline"
                  className="text-danger"
                  disabled={act.isPending || reason.trim().length < 3}
                  onClick={async () => {
                    if (await confirm({ title: t('logistics.trip.cancelTitle'), body: tr.purpose, danger: true, confirmLabel: t('logistics.trip.cancel') })) act.mutate({ path: 'cancel', body: { note: reason } })
                  }}
                >
                  {t('logistics.trip.cancel')}
                </Button>
              </div>
            </section>
          )}
          {act.isError && (
            <p role="alert" className="text-sm text-danger">
              {errorText(t, act.error)}
            </p>
          )}
        </Card>
      )}
    </div>
  )
}
