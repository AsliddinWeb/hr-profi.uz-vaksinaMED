import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Pencil, Phone, PhoneOff, Video } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams, useSearchParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { api, ApiError, send } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { RoomView } from './RoomView'
import { callTitle, durationText, STATUS_TONE, type CallDetail, type TokenResp } from './api'

const LIVE = ['ringing', 'scheduled', 'active']

/** /calls/:id: qo'ng'iroq xonasi (qo'shilish, video/audio, ekran ulashish) yoki tugagan qo'ng'iroq xulosasi. */
export function RoomPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const [sp, setSp] = useSearchParams()
  const qc = useQueryClient()
  const confirm = useConfirm()
  const [tok, setTok] = useState<TokenResp | null>(null)
  const [joinedAt, setJoinedAt] = useState(0)
  const auto = useRef(false)
  const q = useQuery({ queryKey: ['calls', 'one', id], queryFn: () => api<CallDetail>(`/api/v1/calls/${id}`), retry: false, refetchInterval: 2500 })
  const refresh = () => void qc.invalidateQueries({ queryKey: ['calls'] })
  const join = useMutation({
    mutationFn: () => send<TokenResp>('POST', `/api/v1/calls/${id}/token`, {}),
    onSuccess: (r) => {
      setTok(r)
      setJoinedAt(Date.now())
      refresh()
    },
  })
  const act = useMutation({ mutationFn: (path: string) => send('POST', `/api/v1/calls/${id}/${path}`, {}), onSuccess: refresh })
  const d = q.data
  const live = !!d && LIVE.includes(d.status)

  const leave = useCallback(() => {
    setTok(null)
    void send('POST', `/api/v1/calls/${id}/leave`, {}).finally(refresh)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  // ?join=1 (qabul qilish / yangi qo'ng'iroq): bir marta avtomatik qo'shiladi
  useEffect(() => {
    if (sp.get('join') && d?.can.join && !tok && !auto.current && !join.isPending) {
      auto.current = true
      join.mutate()
      setSp({}, { replace: true })
    }
  }, [sp, d?.can.join, tok, join, setSp])

  // qo'ng'iroq boshqa tomondan tugasa, xonadan chiqamiz
  useEffect(() => {
    if (tok && d && !LIVE.includes(d.status)) setTok(null)
  }, [tok, d])

  // sahifa yopilganda serverga xabar (webhook ham tuzatadi)
  useEffect(() => {
    if (!tok) return
    const bye = () => void fetch(`/api/v1/calls/${id}/leave`, { method: 'POST', keepalive: true, credentials: 'same-origin', headers: { 'X-Requested-With': 'vaksina' } })
    window.addEventListener('pagehide', bye)
    return () => {
      window.removeEventListener('pagehide', bye)
      bye()
    }
  }, [tok, id])

  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!d) return <Skeleton className="mx-auto h-96 max-w-4xl" />
  const waiting = d.status === 'ringing' && d.me?.role === 'host'
  const err = join.isError ? errorText(t, join.error) : act.isError ? errorText(t, act.error) : null

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader
        title={callTitle(d, t('calls.conference'))}
        subtitle={`${t(`calls.kind.${d.kind}`)} · ${t(`calls.media.${d.media}`)}`}
        backTo="/calls"
        backLabel={t('calls.title')}
        actions={
          d.can.edit && !tok ? (
            <Link to={`/calls/${id}/edit`}>
              <Button variant="outline">
                <Pencil className="size-4" />
                {t('common.edit')}
              </Button>
            </Link>
          ) : undefined
        }
      />
      {tok && live ? (
        <RoomView
          tok={tok}
          startedAt={joinedAt}
          canEnd={d.can.end}
          banner={waiting ? t('calls.room.ringing') : undefined}
          onLeave={leave}
          onEnd={async () => {
            if (await confirm({ title: t('calls.room.endAll'), body: t('calls.room.endConfirm'), danger: true, confirmLabel: t('calls.room.endAll') })) {
              setTok(null)
              act.mutate('end')
            }
          }}
        />
      ) : (
        <Card className="flex flex-col gap-5 p-6">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={STATUS_TONE[d.status] ?? 'neutral'}>{t(`calls.status.${d.status}`)}</Badge>
            {d.status === 'active' && <span className="text-sm text-muted">{t('calls.online', { count: d.online })}</span>}
          </div>
          <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
            <Info label={t('calls.host')}>{d.host?.name ?? '—'}</Info>
            <Info label={t('calls.when')}>{formatDateTime(d.scheduled_at ?? d.started_at ?? d.created_at, i18n.language)}</Info>
            <Info label={t('calls.duration')}>{durationText(d.duration)}</Info>
            {d.end_reason && <Info label={t('calls.endReason')}>{t(`calls.reason.${d.end_reason}`)}</Info>}
          </dl>
          {live && (
            <div className="flex flex-wrap items-center gap-2 border-t border-border pt-4">
              {d.can.join && (
                <Button disabled={join.isPending} onClick={() => join.mutate()}>
                  {d.media === 'video' ? <Video className="size-4" /> : <Phone className="size-4" />}
                  {d.me?.status === 'joined' || d.me?.status === 'left' ? t('calls.rejoin') : t('calls.join')}
                </Button>
              )}
              {d.can.decline && (
                <Button variant="outline" className="text-danger" disabled={act.isPending} onClick={() => act.mutate('decline')}>
                  <PhoneOff className="size-4" />
                  {t('calls.decline')}
                </Button>
              )}
              {d.can.end && (
                <Button
                  variant="outline"
                  className="text-danger"
                  disabled={act.isPending}
                  onClick={async () => {
                    if (await confirm({ title: t('calls.room.endAll'), body: t('calls.room.endConfirm'), danger: true, confirmLabel: t('calls.room.endAll') })) act.mutate('end')
                  }}
                >
                  {t('calls.room.endAll')}
                </Button>
              )}
            </div>
          )}
          {err && <p role="alert" className="text-sm text-danger">{err}</p>}
        </Card>
      )}
      <Card className="overflow-hidden">
        <h2 className="px-5 pt-5 font-semibold">{t('calls.participants')}</h2>
        <div className="overflow-x-auto">
          <table className="mt-3 w-full text-left text-sm">
            <thead className="border-y border-border text-xs text-muted">
              <tr>
                <th className="px-5 py-2.5 font-medium">{t('calls.participant')}</th>
                <th className="px-5 py-2.5 font-medium">{t('attendance.statusLabel')}</th>
                <th className="hidden px-5 py-2.5 font-medium sm:table-cell">{t('calls.joinedAt')}</th>
                <th className="px-5 py-2.5 text-right font-medium">{t('calls.duration')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {d.participants.map((p) => (
                <tr key={p.user_id}>
                  <td className="px-5 py-2.5 font-medium">
                    {p.name}
                    {p.role === 'host' && <span className="ml-2 text-xs text-muted">{t('calls.host')}</span>}
                  </td>
                  <td className="px-5 py-2.5 text-muted">{t(`calls.pstatus.${p.status}`)}</td>
                  <td className="hidden px-5 py-2.5 tabular-nums text-muted sm:table-cell">{p.first_joined_at ? formatDateTime(p.first_joined_at, i18n.language) : '—'}</td>
                  <td className="px-5 py-2.5 text-right tabular-nums">{durationText(p.seconds)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

function Info({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="mt-1">{children}</dd>
    </div>
  )
}
