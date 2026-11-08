import { useMutation, useQuery } from '@tanstack/react-query'
import type { Room } from 'livekit-client'
import { Camera, CheckCircle2, Circle, Eye, Lock, Radio, Video, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, send } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { errorText } from '../auth/errorText'
import { fmtSec, livekitUrl, type LiveToken, type ResultRow, type Session } from './api'

/** Natijalar: stajyorlar bo'yicha bosqichlar, ko'rilgan vaqt, test bali, kuzatuv sessiyalari (jonli, yozuv, suratlar). */
export function Results({ trackId }: { trackId: number }) {
  const { t, i18n } = useTranslation()
  const q = useQuery({ queryKey: ['preboarding', 'results', trackId], queryFn: () => api<{ items: ResultRow[] }>(`/api/v1/preboarding/tracks/${trackId}/results`), refetchInterval: 15_000 })
  const [open, setOpen] = useState<number | null>(null)
  const [live, setLive] = useState<Session | null>(null)
  if (!q.data) return <Skeleton className="h-64" />
  if (!q.data.items.length) return <Card className="p-8 text-center text-sm text-muted">{t('preboarding.noInterns')}</Card>
  return (
    <div className="flex flex-col gap-3">
      {live && <LiveViewer session={live} onClose={() => setLive(null)} />}
      {q.data.items.map((r) => (
        <Card key={r.id} className="flex flex-col gap-3 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold">{r.employee?.full_name ?? '—'}</span>
            <Badge tone={r.status === 'active' ? 'info' : r.status === 'ready' || r.status === 'completed' ? 'success' : 'neutral'}>{t(`preboarding.status.${r.status}`, { defaultValue: r.status })}</Badge>
            {r.live && (
              <Badge tone="danger">
                <Radio className="size-3 animate-pulse" /> {t('preboarding.liveNow')}
              </Badge>
            )}
            {!r.consent && <Badge tone="warning">{t('preboarding.noConsent')}</Badge>}
            <span className="ml-auto text-xs text-muted">
              {r.summary.done}/{r.summary.required} · {r.summary.percent}%{r.summary.avg_score != null ? ` · ${t('preboarding.avgScore', { s: r.summary.avg_score })}` : ''}
            </span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-surface-3">
            <div className="h-full bg-success" style={{ width: `${r.summary.percent}%` }} />
          </div>
          <ol className="grid gap-1.5 text-xs sm:grid-cols-2">
            {r.stages.map((s) => (
              <li key={s.id} className="flex items-start gap-2 rounded-control bg-surface-2 px-2.5 py-1.5">
                {s.state === 'done' ? <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-success" /> : s.state === 'locked' ? <Lock className="mt-0.5 size-3.5 shrink-0 text-muted" /> : <Circle className="mt-0.5 size-3.5 shrink-0 text-info" />}
                <span className="min-w-0">
                  <span className="block truncate font-medium">{s.title}</span>
                  <span className="text-muted">
                    {s.req.video && `${t('preboarding.r.video')} ${fmtSec(s.req.video.seen)}/${fmtSec(s.req.video.need)} `}
                    {s.req.slides && `· ${t('preboarding.r.slides')} ${fmtSec(s.req.slides.seen)}/${fmtSec(s.req.slides.need)} `}
                    {s.req.test && `· ${t('preboarding.r.test')} ${s.req.test.score ?? '—'}% (${s.req.test.attempts})`}
                  </span>
                </span>
              </li>
            ))}
          </ol>
          {r.sessions.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <div className="text-xs font-semibold text-muted">{t('preboarding.sessions')}</div>
              {r.sessions.map((s) => (
                <div key={s.id} className="flex flex-wrap items-center gap-2 rounded-control border border-border px-2.5 py-1.5 text-xs">
                  <span className="font-medium">{s.step ?? '—'}</span>
                  <span className="text-muted">{formatDateTime(s.started_at, i18n.language)} · {fmtSec(s.seconds)}</span>
                  <span className="text-muted">
                    <Video className="inline size-3" /> {s.clips} · <Camera className="inline size-3" /> {s.snapshots}
                  </span>
                  {s.events.length > 0 && <Badge tone="warning">{t('preboarding.events', { n: s.events.length })}</Badge>}
                  <span className="ml-auto flex gap-1.5">
                    {s.live && (
                      <Button className="h-7 px-2.5 text-xs" onClick={() => setLive(s)}>
                        <Eye className="size-3.5" />
                        {t('preboarding.watchLive')}
                      </Button>
                    )}
                    <Button variant="outline" className="h-7 px-2.5 text-xs" onClick={() => setOpen(open === s.id ? null : s.id)}>
                      {t('preboarding.recordings')}
                    </Button>
                  </span>
                  {open === s.id && <SessionMedia id={s.id} />}
                </div>
              ))}
            </div>
          )}
        </Card>
      ))}
    </div>
  )
}

function SessionMedia({ id }: { id: number }) {
  const { t, i18n } = useTranslation()
  const q = useQuery({
    queryKey: ['preboarding', 'monitor', id],
    queryFn: () => api<{ clip_list: { i: number; at: string }[]; snapshot_list: { i: number; at: string }[]; events: { at: string; kind: string }[] }>(`/api/v1/preboarding/monitor/${id}`),
  })
  if (!q.data) return <Skeleton className="h-24 w-full" />
  const d = q.data
  return (
    <div className="flex w-full flex-col gap-3 pt-2">
      {d.events.length > 0 && (
        <ul className="flex flex-wrap gap-1.5">
          {d.events.map((e, k) => (
            <li key={k} className="rounded bg-warning/10 px-1.5 py-0.5 text-[11px] text-warning">
              {formatDateTime(e.at, i18n.language).slice(-5)} · {t(`preboarding.ev.${e.kind}`, { defaultValue: e.kind })}
            </li>
          ))}
        </ul>
      )}
      {d.clip_list.length > 0 ? (
        <div className="grid gap-2 sm:grid-cols-2">
          {d.clip_list.map((c) => (
            <figure key={c.i}>
              <video src={`/api/v1/preboarding/monitor/${id}/clip/${c.i}`} controls preload="none" className="aspect-video w-full rounded-control bg-black" />
              <figcaption className="text-[11px] text-muted">{formatDateTime(c.at, i18n.language)}</figcaption>
            </figure>
          ))}
        </div>
      ) : (
        <p className="text-xs text-muted">{t('preboarding.noClips')}</p>
      )}
      {d.snapshot_list.length > 0 && (
        <div className="grid grid-cols-4 gap-1.5 sm:grid-cols-6">
          {d.snapshot_list.map((s) => (
            <a key={s.i} href={`/api/v1/preboarding/monitor/${id}/snapshot/${s.i}`} target="_blank" rel="noreferrer" title={formatDateTime(s.at, i18n.language)}>
              <img src={`/api/v1/preboarding/monitor/${id}/snapshot/${s.i}`} alt="" loading="lazy" className="aspect-[4/3] w-full rounded object-cover" />
            </a>
          ))}
        </div>
      )}
    </div>
  )
}

/** Jonli ko'rish va eshitish (yashirin tomoshabin, LiveKit). */
function LiveViewer({ session, onClose }: { session: Session; onClose: () => void }) {
  const { t } = useTranslation()
  const toast = useToast()
  const box = useRef<HTMLDivElement>(null)
  const [state, setState] = useState<'connecting' | 'live' | 'waiting'>('connecting')
  const token = useMutation({ mutationFn: () => send<LiveToken>('POST', `/api/v1/preboarding/monitor/${session.id}/watch`, {}) })

  useEffect(() => {
    let room: Room | null = null
    let alive = true
    void (async () => {
      try {
        const tok = await token.mutateAsync()
        const mod = await import('livekit-client')
        room = new mod.Room({ adaptiveStream: true })
        const attach = (track: { attach: () => HTMLMediaElement; kind: string }) => {
          const el = track.attach()
          if (track.kind === 'video') el.className = 'aspect-video w-full rounded-control bg-black object-contain'
          box.current?.appendChild(el)
          setState('live')
        }
        room.on(mod.RoomEvent.TrackSubscribed, (track) => attach(track as unknown as { attach: () => HTMLMediaElement; kind: string }))
        room.on(mod.RoomEvent.TrackUnsubscribed, (track) => track.detach().forEach((el) => el.remove()))
        await room.connect(livekitUrl(tok), tok.token)
        if (!alive) return void room.disconnect()
        if (!room.remoteParticipants.size) setState('waiting')
      } catch (e) {
        toast.push({ title: errorText(t, e), tone: 'danger' })
        onClose()
      }
    })()
    return () => {
      alive = false
      void room?.disconnect()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session.id])

  return (
    <Card className="flex flex-col gap-2 p-3">
      <div className="flex items-center gap-2">
        <Radio className="size-4 animate-pulse text-danger" />
        <span className="text-sm font-semibold">{t('preboarding.liveTitle', { step: session.step ?? '' })}</span>
        <button type="button" onClick={onClose} aria-label={t('common.close')} className="ml-auto grid size-8 place-items-center rounded-full hover:bg-surface-2">
          <X className="size-4" />
        </button>
      </div>
      <div ref={box} className="flex flex-col gap-2" />
      {state !== 'live' && <p className="text-xs text-muted">{t(state === 'waiting' ? 'preboarding.liveWaiting' : 'preboarding.liveConnecting')}</p>}
      <p className="text-[11px] text-muted">{t('preboarding.liveHint')}</p>
    </Card>
  )
}
