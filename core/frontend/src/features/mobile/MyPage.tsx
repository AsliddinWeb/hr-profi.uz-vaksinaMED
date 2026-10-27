import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BatteryMedium, MapPin, Play, ShieldCheck, Siren, Square } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { api, send } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { getPosition } from '../attendance/geo'
import { errorText } from '../auth/errorText'
import { useMobileTracker } from './useMobileTracker'
import type { My, Session } from './api'

/** /mobile/my: xodim sahifasi (telefon): rozilik, ish kunini boshlash/tugatish, kuzatuv holati va SOS. */
export function MyPage() {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const confirm = useConfirm()
  const q = useQuery({ queryKey: ['mobile', 'my'], queryFn: () => api<My>('/api/v1/mobile/my'), refetchInterval: 60_000 })
  const refresh = () => void qc.invalidateQueries({ queryKey: ['mobile'] })
  const tracker = useMobileTracker(q.data?.session?.status === 'active', q.data?.permit?.interval_s ?? 60, refresh)
  const [sosSent, setSosSent] = useState(false)
  const consent = useMutation({ mutationFn: () => send('POST', '/api/v1/mobile/my/consent'), onSuccess: refresh })
  const revoke = useMutation({ mutationFn: () => send('DELETE', '/api/v1/mobile/my/consent'), onSuccess: refresh })
  const start = useMutation({
    mutationFn: async () => {
      let pos: { lat: number; lng: number } | null = null
      let permission: 'granted' | 'denied' = 'granted'
      try {
        pos = await getPosition()
      } catch (e) {
        if (e instanceof Error && e.message === 'denied') permission = 'denied'
      }
      const b = await (navigator as unknown as { getBattery?: () => Promise<{ level: number }> }).getBattery?.().catch(() => null)
      return send<Session>('POST', '/api/v1/mobile/my/start', { lat: pos?.lat ?? null, lng: pos?.lng ?? null, permission, battery: b ? Math.round(b.level * 100) : null })
    },
    onSuccess: refresh,
  })
  const stop = useMutation({
    mutationFn: async () => {
      const pos = await getPosition().catch(() => null)
      return send('POST', '/api/v1/mobile/my/stop', { lat: pos?.lat ?? null, lng: pos?.lng ?? null })
    },
    onSuccess: refresh,
  })
  const sos = useMutation({
    mutationFn: async () => {
      const pos = await getPosition().catch(() => null)
      return send('POST', '/api/v1/mobile/my/sos', { lat: pos?.lat ?? tracker.last?.lat ?? null, lng: pos?.lng ?? tracker.last?.lng ?? null, battery: tracker.battery })
    },
    onSuccess: () => setSosSent(true),
  })
  if (!q.data) return <Skeleton className="mx-auto h-96 max-w-xl" />
  const m = q.data
  const s = m.session
  return (
    <div className="mx-auto flex max-w-xl flex-col gap-4">
      <PageHeader title={t('mobile.my.title')} subtitle={m.employee.name} />
      {m.reason === 'no_permit' && <Card className="p-5 text-center text-sm text-muted">{t('mobile.my.noPermit')}</Card>}

      {m.permit && (
        <Card className="flex flex-col gap-3 p-5">
          <div className="flex items-center gap-2 font-semibold">
            <ShieldCheck className="size-5" />
            {t('mobile.my.privacy')}
          </div>
          <ul className="list-disc pl-5 text-sm text-muted">
            <li>{t('mobile.my.p1', { start: m.permit.window_start, end: m.permit.window_end })}</li>
            <li>{t('mobile.my.p2')}</li>
            <li>{t('mobile.my.p3', { days: m.privacy.retention_days })}</li>
            <li>{t('mobile.my.p4')}</li>
          </ul>
          {m.permit.consent_at ? (
            <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <Badge tone="success">{t('mobile.my.consented', { date: formatDateTime(m.permit.consent_at, i18n.language) })}</Badge>
              <Button variant="ghost" className="text-danger" disabled={revoke.isPending} onClick={async () => { if (await confirm({ title: t('mobile.my.revoke'), body: t('mobile.my.revokeHint'), danger: true, confirmLabel: t('mobile.my.revoke') })) revoke.mutate() }}>
                {t('mobile.my.revoke')}
              </Button>
            </div>
          ) : (
            <Button disabled={consent.isPending} onClick={() => consent.mutate()}>
              {t('mobile.my.consent')}
            </Button>
          )}
        </Card>
      )}

      {m.permit?.consent_at && !s && (
        <Card className="flex flex-col gap-3 p-5">
          <p className="text-sm text-muted">{m.reason === 'outside_hours' ? t('mobile.my.outside', { start: m.permit.window_start, end: m.permit.window_end }) : t('mobile.my.startHint')}</p>
          <Button className="h-12 text-base" disabled={!m.can_start || start.isPending} onClick={() => start.mutate()}>
            <Play className="size-5" />
            {t('mobile.my.start')}
          </Button>
        </Card>
      )}

      {s && (
        <Card tint="mint" className="flex flex-col gap-4 p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="font-semibold">{t('mobile.my.dayActive')}</div>
              <div className="text-xs text-muted">{t('mobile.my.since', { time: formatDateTime(s.started_at, i18n.language) })}</div>
            </div>
            <Badge tone="warning">{t('mobile.my.live')}</Badge>
          </div>
          <div className="rounded-control bg-surface p-3 text-sm">
            <div className="flex items-center gap-2 font-medium">
              <MapPin className="size-4" />
              {t(`mobile.my.state.${tracker.state}`)}
            </div>
            <div className="mt-1 text-xs text-muted tabular-nums">
              {tracker.last ? `${tracker.last.lat.toFixed(5)}, ${tracker.last.lng.toFixed(5)} · ±${Math.round(tracker.last.accuracy ?? 0)} m · ` : ''}
              {t('mobile.my.sent', { sent: tracker.sent, queued: tracker.queued })}
            </div>
            <div className="mt-1 flex items-center gap-1 text-xs text-muted">
              <BatteryMedium className="size-4" />
              {tracker.battery === null ? t('mobile.my.batteryUnknown') : `${tracker.battery}%`}
            </div>
            {tracker.state === 'denied' && <p className="mt-1 text-xs text-danger">{t('mobile.my.denied')}</p>}
          </div>
          <Button variant="outline" className="h-12 text-base" disabled={stop.isPending} onClick={() => stop.mutate()}>
            <Square className="size-5" />
            {t('mobile.my.stop')}
          </Button>
        </Card>
      )}

      {m.permit?.consent_at && (
        <Card className="flex flex-col gap-2 p-5">
          <Button
            className="h-12 bg-danger text-base text-white"
            disabled={sos.isPending}
            onClick={async () => {
              if (await confirm({ title: t('mobile.my.sos'), body: t('mobile.my.sosConfirm'), danger: true, confirmLabel: t('mobile.my.sosSend') })) sos.mutate()
            }}
          >
            <Siren className="size-5" />
            {t('mobile.my.sos')}
          </Button>
          {sosSent && (
            <p role="status" className="text-center text-sm text-success">
              {t('mobile.my.sosSent')}
            </p>
          )}
        </Card>
      )}
      {(consent.isError || revoke.isError || start.isError || stop.isError || sos.isError) && (
        <p role="alert" className="text-sm text-danger">
          {errorText(t, consent.error ?? revoke.error ?? start.error ?? stop.error ?? sos.error)}
        </p>
      )}
    </div>
  )
}
