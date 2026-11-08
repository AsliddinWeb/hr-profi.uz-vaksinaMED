import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CameraOff, CheckCircle2, FileText, Lock, Mic, PlayCircle, ShieldCheck, Video } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, send } from '../../lib/api'
import { cn } from '../../lib/cn'
import { errorText } from '../auth/errorText'
import { fmtSec, type LiveToken, type Monitoring, type MyData, type MyStage, type Stage } from './api'
import { useMonitor } from './useMonitor'

const TICK_MS = 10_000

/* ---------- Admin: «Ko'rish» (stajyor ko'radigan ko'rinish, kuzatuvsiz) ---------- */

export function LessonPreview({ stage }: { stage: Stage }) {
  const { t } = useTranslation()
  const m = stage.media
  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex items-center gap-2">
        <h3 className="font-semibold">{stage.title}</h3>
        <Badge>{t(`preboarding.aud.${stage.audience}`)}</Badge>
      </div>
      {stage.description && <p className="whitespace-pre-wrap text-sm text-muted">{stage.description}</p>}
      {m.video.kind === 'youtube' && <iframe src={`https://www.youtube-nocookie.com/embed/${m.video.id}`} title={stage.title} className="aspect-video w-full rounded-card" allow="fullscreen" allowFullScreen />}
      {m.video.embed && <iframe src={m.video.embed} title={stage.title} className="aspect-video w-full rounded-card border border-border" allow="autoplay" />}
      {m.slides.embed && <iframe src={m.slides.embed} title={t('preboarding.r.slides')} className="h-[60vh] w-full rounded-card border border-border" />}
      {stage.questions.map((q, i) => (
        <div key={q.id} className="rounded-card bg-surface-2 p-3 text-sm">
          <div className="font-medium">
            {i + 1}. {q.text}
          </div>
          <ul className="mt-1 space-y-0.5">
            {q.options.map((o, k) => (
              <li key={k} className={cn(q.correct?.includes(k) && 'font-semibold text-success')}>
                {String.fromCharCode(65 + k)}) {o}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </Card>
  )
}

/* ---------- Stajyor paneli ---------- */

/** /preboarding/my: stajyorning o'z prebordingi — faqat o'z lavozimi darslari, ketma-ket, kamera nazorati bilan. */
export function MyPreboardingPage() {
  const { t } = useTranslation()
  const toast = useToast()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['preboarding', 'my'], queryFn: () => api<MyData | null>('/api/v1/preboarding/my') })
  const [sel, setSel] = useState<number | null>(null)
  const consent = useMutation({
    mutationFn: () => send<MyData>('POST', '/api/v1/preboarding/my/consent', {}),
    onSuccess: (d) => qc.setQueryData(['preboarding', 'my'], d),
    onError: (e) => toast.push({ title: errorText(t, e), tone: 'danger' }),
  })
  if (q.isLoading) return <Skeleton className="mx-auto h-96 max-w-4xl" />
  const d = q.data
  if (!d) return <Card className="mx-auto max-w-xl p-8 text-center text-sm text-muted">{t('preboarding.my.none')}</Card>
  const current = d.stages.find((s) => s.id === sel) ?? d.stages.find((s) => s.state === 'available') ?? d.stages[0]
  const needConsent = d.monitoring.camera && !d.enrollment.consent

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4">
      <section className="rounded-card bg-gradient-to-br from-[#1f3a68] to-[#2a4f8f] p-5 text-white shadow-card">
        <div className="text-sm text-white/70">{d.program.position}</div>
        <h1 className="text-2xl font-bold">{t('preboarding.my.title')}</h1>
        {d.program.description && <p className="mt-1 whitespace-pre-wrap text-sm text-white/80">{d.program.description}</p>}
        <div className="mt-4 flex items-center gap-3">
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/20">
            <div className="h-full bg-emerald-400" style={{ width: `${d.summary.percent}%` }} />
          </div>
          <span className="text-sm font-semibold">
            {d.summary.done}/{d.summary.required}
          </span>
        </div>
        {d.enrollment.status === 'ready' && <p className="mt-2 text-sm font-semibold text-emerald-300">{t('preboarding.my.ready')}</p>}
      </section>

      {needConsent && (
        <Card className="flex flex-col gap-3 border border-warning/40 p-5">
          <div className="flex items-center gap-2 font-semibold">
            <ShieldCheck className="size-5 text-warning" />
            {t('preboarding.consent.title')}
          </div>
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
            {d.monitoring.camera && <li>{t('preboarding.consent.camera')}</li>}
            {d.monitoring.live && <li>{t('preboarding.consent.live')}</li>}
            {d.monitoring.record && <li>{t('preboarding.consent.record')}</li>}
            {d.monitoring.snapshots && <li>{t('preboarding.consent.snapshots')}</li>}
            <li>{t('preboarding.consent.retention')}</li>
          </ul>
          <Button className="self-start" disabled={consent.isPending} onClick={() => consent.mutate()}>
            {t('preboarding.consent.agree')}
          </Button>
        </Card>
      )}

      <div className="flex flex-wrap gap-2">
        {d.stages.map((s, i) => (
          <button
            key={s.id}
            type="button"
            disabled={s.state === 'locked'}
            onClick={() => setSel(s.id)}
            className={cn(
              'relative flex w-14 flex-col items-center rounded-card border py-1.5 transition disabled:cursor-not-allowed disabled:opacity-50',
              s.id === current?.id ? 'border-[#1f3a68] bg-[#1f3a68] text-white' : 'border-border bg-surface hover:bg-surface-2',
            )}
          >
            <span className="text-[9px] font-semibold uppercase opacity-70">{t('preboarding.stage')}</span>
            <span className="text-lg font-bold leading-none">{i + 1}</span>
            {s.state === 'done' && <CheckCircle2 className="absolute -right-1.5 -top-1.5 size-4 rounded-full bg-surface text-success" />}
            {s.state === 'locked' && <Lock className="absolute -right-1.5 -top-1.5 size-4 rounded-full bg-surface p-0.5 text-muted" />}
          </button>
        ))}
      </div>

      {current && <Lesson key={current.id} stage={current} data={d} blocked={needConsent} />}
    </div>
  )
}

function Lesson({ stage, data, blocked }: { stage: MyStage; data: MyData; blocked: boolean }) {
  const { t } = useTranslation()
  const toast = useToast()
  const qc = useQueryClient()
  const [session, setSession] = useState<{ monitor_id: number | null; live: LiveToken | null; monitoring: Monitoring } | null>(null)
  const hasVideo = !!stage.media.video.kind
  const hasSlides = !!stage.media.slides.embed
  const hasTest = stage.question_count > 0
  const [pane, setPane] = useState<'video' | 'slides' | 'test'>(hasVideo ? 'video' : hasSlides ? 'slides' : 'test')
  const setData = (d: MyData) => qc.setQueryData(['preboarding', 'my'], d)
  const start = useMutation({
    mutationFn: () => send<{ monitor_id: number | null; live: LiveToken | null; monitoring: Monitoring }>('POST', `/api/v1/preboarding/my/stages/${stage.id}/start`, {}),
    onSuccess: setSession,
    onError: (e) => toast.push({ title: errorText(t, e), tone: 'danger' }),
  })
  const read = useMutation({
    mutationFn: () => send<MyData>('POST', `/api/v1/preboarding/my/stages/${stage.id}/done`, {}),
    onSuccess: setData,
    onError: (e) => toast.push({ title: errorText(t, e), tone: 'danger' }),
  })
  const monitor = useMonitor(session?.monitor_id ?? null, session?.monitoring ?? data.monitoring, session?.live ?? null)
  const mediaDone = (!stage.req.video || stage.req.video.done) && (!stage.req.slides || stage.req.slides.done)
  const needsCamera = data.monitoring.camera
  const running = !!session && (!needsCamera || monitor.cameraOk)

  const tick = async (kind: 'video' | 'slides', delta: number, pos?: number, duration?: number) => {
    if (!session) return
    try {
      const r = await send<MyData & { counted: boolean }>('POST', `/api/v1/preboarding/my/stages/${stage.id}/tick`, {
        kind, delta: Math.round(delta), pos: pos != null ? Math.floor(pos) : null, duration: duration ? Math.round(duration) : null,
        monitor_id: session.monitor_id, camera_ok: monitor.cameraOk, event: monitor.takeEvent(),
      }) // prettier-ignore
      setData(r)
    } catch {
      /* tarmoq: keyingi tick yuboradi */
    }
  }

  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="grid size-8 place-items-center rounded-control bg-[#1f3a68] text-white">
          <Video className="size-4" />
        </span>
        <h2 className="font-semibold">{stage.title}</h2>
        {stage.state === 'done' && <Badge tone="success">{t('preboarding.my.done')}</Badge>}
      </div>
      {stage.description && <p className="whitespace-pre-wrap text-sm text-muted">{stage.description}</p>}

      {!hasVideo && !hasSlides && !hasTest ? (
        stage.state !== 'done' && (
          <Button className="self-start" disabled={read.isPending} onClick={() => read.mutate()}>
            <CheckCircle2 className="size-4" />
            {t('preboarding.my.acknowledge')}
          </Button>
        )
      ) : stage.state === 'done' ? (
        <p className="text-sm text-success">{t('preboarding.my.stageDone', { score: stage.score ?? '—' })}</p>
      ) : !session ? (
        <div className="flex flex-col items-start gap-2">
          {stage.media.video.thumb && <img src={stage.media.video.thumb} alt="" className="aspect-video w-full rounded-card object-cover" />}
          <Button disabled={blocked || start.isPending} onClick={() => start.mutate()}>
            <PlayCircle className="size-4" />
            {t('preboarding.my.start')}
          </Button>
          {needsCamera && <p className="text-xs text-muted">{t('preboarding.my.cameraNote')}</p>}
        </div>
      ) : (
        <>
          {needsCamera && !monitor.cameraOk && (
            <div className="flex items-start gap-2 rounded-control border border-danger/30 bg-danger/10 p-3 text-sm text-danger" role="alert">
              <CameraOff className="mt-0.5 size-4 shrink-0" />
              {t(monitor.error === 'denied' ? 'preboarding.my.cameraDenied' : 'preboarding.my.cameraNeeded')}
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            {hasVideo && <PaneBtn active={pane === 'video'} done={!!stage.req.video?.done} onClick={() => setPane('video')} label={t('preboarding.r.video')} />}
            {hasSlides && <PaneBtn active={pane === 'slides'} done={!!stage.req.slides?.done} onClick={() => setPane('slides')} label={t('preboarding.r.slides')} />}
            {hasTest && <PaneBtn active={pane === 'test'} done={!!stage.req.test?.done} disabled={!mediaDone} onClick={() => setPane('test')} label={t('preboarding.r.test')} />}
          </div>
          {pane === 'video' && hasVideo && <VideoPane stage={stage} running={running} onTick={(dlt, pos, dur) => tick('video', dlt, pos, dur)} />}
          {pane === 'slides' && hasSlides && <SlidesPane stage={stage} running={running} onTick={(dlt) => tick('slides', dlt)} />}
          {pane === 'test' && hasTest && mediaDone && <TestPane stage={stage} onResult={setData} />}
          {!mediaDone && hasTest && <p className="text-xs text-muted">{t('preboarding.my.testAfter')}</p>}
        </>
      )}

      {session && monitor.stream && <CameraBubble stream={monitor.stream} recording={monitor.recording} live={monitor.live} />}
    </Card>
  )
}

function PaneBtn({ active, done, disabled, onClick, label }: { active: boolean; done: boolean; disabled?: boolean; onClick: () => void; label: string }) {
  return (
    <button type="button" disabled={disabled} onClick={onClick} className={cn('inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-semibold disabled:opacity-40', active ? 'bg-[#1f3a68] text-white' : 'border border-border bg-surface hover:bg-surface-2')}>
      {done ? <CheckCircle2 className="size-3.5 text-success" /> : disabled ? <Lock className="size-3.5" /> : null}
      {label}
    </button>
  )
}

/* ---------- Video: YouTube IFrame API (oldinga o'tkazib bo'lmaydi) yoki Drive ---------- */

interface YTPlayer {
  getCurrentTime(): number
  getDuration(): number
  getPlayerState(): number
  getPlaybackRate(): number
  seekTo(s: number, allow: boolean): void
  pauseVideo(): void
  destroy(): void
}
type YTNs = { Player: new (el: HTMLElement, o: Record<string, unknown>) => YTPlayer }

let ytReady: Promise<YTNs> | null = null
function loadYT(): Promise<YTNs> {
  const w = window as unknown as { YT?: YTNs; onYouTubeIframeAPIReady?: () => void }
  if (w.YT?.Player) return Promise.resolve(w.YT)
  ytReady ??= new Promise((resolve) => {
    w.onYouTubeIframeAPIReady = () => resolve(w.YT!)
    const s = document.createElement('script')
    s.src = 'https://www.youtube.com/iframe_api'
    document.head.appendChild(s)
  })
  return ytReady
}

function VideoPane({ stage, running, onTick }: { stage: MyStage; running: boolean; onTick: (delta: number, pos?: number, duration?: number) => void }) {
  const { t } = useTranslation()
  const el = useRef<HTMLDivElement>(null)
  const player = useRef<YTPlayer | null>(null)
  const acc = useRef(0)
  const maxPos = useRef(stage.req.video?.seen ?? 0)
  const runRef = useRef(running)
  const tickRef = useRef(onTick)
  useEffect(() => {
    runRef.current = running
    tickRef.current = onTick
  })
  const yt = stage.media.video.kind === 'youtube'

  useEffect(() => {
    if (!yt || !el.current) return
    let alive = true
    void loadYT().then((YT) => {
      if (!alive || !el.current) return
      player.current = new YT.Player(el.current, {
        videoId: stage.media.video.id,
        host: 'https://www.youtube-nocookie.com',
        playerVars: { rel: 0, modestbranding: 1, disablekb: 1, playsinline: 1 },
      })
    })
    return () => {
      alive = false
      player.current?.destroy()
      player.current = null
    }
  }, [yt, stage.media.video.id])

  // Har soniya: o'ynayapti, oyna ko'rinib turibdi, 1x tezlik, kamera yoqiq bo'lsa hisoblanadi; oldinga sakrash qaytariladi
  useEffect(() => {
    const sec = window.setInterval(() => {
      const visible = document.visibilityState === 'visible'
      if (yt) {
        const p = player.current
        if (!p?.getPlayerState) return
        const pos = p.getCurrentTime()
        if (pos > maxPos.current + 3) p.seekTo(maxPos.current, true)
        if (!runRef.current && p.getPlayerState() === 1) p.pauseVideo()
        if (p.getPlayerState() === 1 && visible && runRef.current && p.getPlaybackRate() <= 1) {
          acc.current += 1
          maxPos.current = Math.max(maxPos.current, pos)
        }
      } else if (visible && runRef.current) acc.current += 1
    }, 1000)
    const send_ = window.setInterval(() => {
      if (acc.current <= 0) return
      const d = acc.current
      acc.current = 0
      const p = player.current
      tickRef.current(d, yt && p ? p.getCurrentTime() : undefined, yt && p ? p.getDuration() : undefined)
    }, TICK_MS)
    return () => {
      window.clearInterval(sec)
      window.clearInterval(send_)
      if (acc.current > 0) tickRef.current(acc.current)
    }
  }, [yt])

  const r = stage.req.video
  return (
    <div className="flex flex-col gap-2">
      {yt ? <div className="aspect-video w-full overflow-hidden rounded-card bg-black [&>iframe]:size-full"><div ref={el} /></div> : <iframe src={stage.media.video.embed ?? stage.media.video.url ?? ''} title={stage.title} className="aspect-video w-full rounded-card border border-border" allow="autoplay" />}
      {r && <Progress label={t('preboarding.my.watched')} seen={r.seen} need={r.need} />}
      {yt && <p className="text-[11px] text-muted">{t('preboarding.my.noSkip')}</p>}
    </div>
  )
}

function SlidesPane({ stage, running, onTick }: { stage: MyStage; running: boolean; onTick: (delta: number) => void }) {
  const { t } = useTranslation()
  const acc = useRef(0)
  const runRef = useRef(running)
  const tickRef = useRef(onTick)
  useEffect(() => {
    runRef.current = running
    tickRef.current = onTick
  })
  useEffect(() => {
    const sec = window.setInterval(() => {
      if (document.visibilityState === 'visible' && document.hasFocus() && runRef.current) acc.current += 1
    }, 1000)
    const send_ = window.setInterval(() => {
      if (acc.current <= 0) return
      const d = acc.current
      acc.current = 0
      tickRef.current(d)
    }, TICK_MS)
    return () => {
      window.clearInterval(sec)
      window.clearInterval(send_)
      if (acc.current > 0) tickRef.current(acc.current)
    }
  }, [])
  const r = stage.req.slides
  return (
    <div className="flex flex-col gap-2">
      <iframe src={stage.media.slides.embed ?? ''} title={t('preboarding.r.slides')} className="h-[65vh] w-full rounded-card border border-border" />
      {r && <Progress label={t('preboarding.my.read')} seen={r.seen} need={r.need} />}
      <p className="flex items-center gap-1 text-[11px] text-muted">
        <FileText className="size-3" />
        {t('preboarding.my.slidesNote')}
      </p>
    </div>
  )
}

function Progress({ label, seen, need }: { label: string; seen: number; need: number }) {
  const pct = Math.min(100, Math.round((seen / Math.max(need, 1)) * 100))
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-muted">{label}</span>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-3">
        <div className={cn('h-full', pct >= 100 ? 'bg-success' : 'bg-info')} style={{ width: `${pct}%` }} />
      </div>
      <span className="tabular-nums">
        {fmtSec(Math.min(seen, need))}/{fmtSec(need)}
      </span>
    </div>
  )
}

/* ---------- Test ---------- */

function TestPane({ stage, onResult }: { stage: MyStage; onResult: (d: MyData) => void }) {
  const { t } = useTranslation()
  const toast = useToast()
  const [ans, setAns] = useState<Record<string, number[]>>({})
  const [res, setRes] = useState<{ score: number; passed: boolean; wrong: string[]; threshold: number } | null>(null)
  const submit = useMutation({
    mutationFn: () => send<MyData & { score: number; passed: boolean; wrong: string[]; threshold: number }>('POST', `/api/v1/preboarding/my/stages/${stage.id}/submit`, { answers: ans }),
    onSuccess: (r) => {
      setRes(r)
      onResult(r)
    },
    onError: (e) => toast.push({ title: errorText(t, e), tone: 'danger' }),
  })
  const tr = stage.req.test
  const left = tr && tr.max_attempts ? tr.max_attempts - tr.attempts : null
  return (
    <div className="flex flex-col gap-3">
      {stage.questions.map((q, i) => (
        <fieldset key={q.id} className={cn('rounded-card bg-surface-2 p-3', res?.wrong.includes(q.id) && 'ring-2 ring-danger/50')}>
          <legend className="text-sm font-medium">
            {i + 1}. {q.text}
          </legend>
          <div className="mt-2 flex flex-col gap-1.5">
            {q.options.map((o, k) => (
              <label key={k} className="flex cursor-pointer items-center gap-2 rounded-control bg-surface px-3 py-2 text-sm">
                <input
                  type={q.multiple ? 'checkbox' : 'radio'}
                  name={`a-${q.id}`}
                  checked={(ans[q.id] ?? []).includes(k)}
                  onChange={(e) => setAns((a) => ({ ...a, [q.id]: q.multiple ? (e.target.checked ? [...(a[q.id] ?? []), k] : (a[q.id] ?? []).filter((x) => x !== k)) : [k] }))}
                />
                {o}
              </label>
            ))}
          </div>
        </fieldset>
      ))}
      {res && (
        <p role="status" className={cn('text-sm font-semibold', res.passed ? 'text-success' : 'text-danger')}>
          {res.passed ? t('preboarding.my.passed', { score: res.score }) : t('preboarding.my.failed', { score: res.score, th: res.threshold })}
        </p>
      )}
      <div className="flex items-center gap-3">
        <Button disabled={submit.isPending || Object.keys(ans).length < stage.questions.length || left === 0} onClick={() => submit.mutate()}>
          {t('preboarding.my.submit')}
        </Button>
        {left != null && <span className="text-xs text-muted">{t('preboarding.my.attemptsLeft', { n: left })}</span>}
      </div>
    </div>
  )
}

/* ---------- Kichik kamera oynasi ---------- */

function CameraBubble({ stream, recording, live }: { stream: MediaStream; recording: boolean; live: boolean }) {
  const { t } = useTranslation()
  const v = useRef<HTMLVideoElement>(null)
  useEffect(() => {
    if (v.current) v.current.srcObject = stream
  }, [stream])
  return (
    <div className="fixed bottom-4 right-4 z-40 w-36 overflow-hidden rounded-card border-2 border-white bg-black shadow-pop sm:w-44">
      <video ref={v} autoPlay muted playsInline className="aspect-[4/3] w-full -scale-x-100 object-cover" />
      <div className="flex items-center gap-1.5 bg-black/80 px-2 py-1 text-[10px] font-semibold text-white">
        {recording && (
          <span className="inline-flex items-center gap-1">
            <span className="size-1.5 animate-pulse rounded-full bg-red-500" />
            REC
          </span>
        )}
        {live && <span className="text-emerald-300">LIVE</span>}
        <Mic className="ml-auto size-3" />
        <span className="sr-only">{t('preboarding.my.monitored')}</span>
      </div>
    </div>
  )
}
