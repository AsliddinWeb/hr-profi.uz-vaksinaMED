import { useQuery } from '@tanstack/react-query'
import { Camera as CameraIcon, Circle, Eye, Square, SwitchCamera } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { api, send } from '../../lib/api'

type Info = { name: string; kind: 'webcam' | 'phone'; branch: string | null; location: string | null; interval: number }

const LIVE_MS = 1500

/** /camera-station/:token — kompyuter yoki telefon kamerasini panelga ulash. Foydalanuvchi o'zi yoqadi, ekranda doim ko'rinib turadi.
 * Oddiy rejim: daqiqada bir holat + kichik kadr. Panelda kimdir jonli ko'rsa — kadr ~1,5 soniyada. */
export function CameraStationPage() {
  const { t } = useTranslation()
  const token = useParams().token ?? ''
  const info = useQuery({ queryKey: ['camera-station', token], queryFn: () => api<Info>(`/api/v1/public/camera/${token}`), retry: false })
  const video = useRef<HTMLVideoElement>(null)
  const stream = useRef<MediaStream | null>(null)
  const timer = useRef<number | null>(null)
  const interval = useRef(60)
  const [on, setOn] = useState(false)
  const [live, setLive] = useState(false)
  const [facing, setFacing] = useState<'user' | 'environment'>('environment')
  const [last, setLast] = useState<Date | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    interval.current = info.data?.interval ?? 60
  }, [info.data])

  const frame = (fast: boolean) => {
    const v = video.current
    if (!v || !v.videoWidth) return undefined
    const c = document.createElement('canvas')
    const w = fast ? 640 : 480
    c.width = w
    c.height = Math.round((v.videoHeight / v.videoWidth) * w)
    c.getContext('2d')?.drawImage(v, 0, 0, c.width, c.height)
    return c.toDataURL('image/jpeg', fast ? 0.55 : 0.6)
  }

  // har bir yuborishdan keyin keyingisi rejalashtiriladi: jonli bo'lsa 1,5 soniya, aks holda interval
  const tickRef = useRef<(fast: boolean) => void>(() => undefined)
  useEffect(() => {
    tickRef.current = (fast: boolean) =>
      void (async () => {
        let next = false
        try {
          const r = await send<{ live?: boolean }>('POST', `/api/v1/public/camera/${token}/beat`, { device: navigator.userAgent.slice(0, 200), snapshot: frame(fast) })
          next = !!r?.live
          setLive(next)
          setLast(new Date())
          setError('')
        } catch {
          setError(t('cst.sendError'))
        }
        if (stream.current) timer.current = window.setTimeout(() => tickRef.current(next), next ? LIVE_MS : interval.current * 1000)
      })()
  }, [token, t])

  const stop = useCallback(
    async (notify = true) => {
      if (timer.current) window.clearTimeout(timer.current)
      timer.current = null
      stream.current?.getTracks().forEach((tr) => tr.stop())
      stream.current = null
      setOn(false)
      setLive(false)
      if (notify) await send('POST', `/api/v1/public/camera/${token}/stop`).catch(() => undefined)
    },
    [token],
  )

  const start = async (mode = facing) => {
    setError('')
    try {
      if (timer.current) window.clearTimeout(timer.current)
      stream.current?.getTracks().forEach((tr) => tr.stop())
      const s = await navigator.mediaDevices.getUserMedia({ video: { facingMode: mode, width: { ideal: 1280 } }, audio: false })
      stream.current = s
      if (video.current) {
        video.current.srcObject = s
        await video.current.play()
      }
      setOn(true)
      timer.current = window.setTimeout(() => tickRef.current(false), 1500)
    } catch {
      setError(t('cst.permission'))
    }
  }

  useEffect(() => () => void stop(false), [stop])
  useEffect(() => {
    // sahifa yopilganda panelga "to'xtadi" signali
    const bye = () => navigator.sendBeacon?.(`/api/v1/public/camera/${token}/stop`)
    window.addEventListener('pagehide', bye)
    return () => window.removeEventListener('pagehide', bye)
  }, [token])

  if (info.isError) {
    return <div className="flex min-h-screen items-center justify-center p-6 text-center text-muted">{t('cst.invalid')}</div>
  }
  const d = info.data
  return (
    <div className="mx-auto flex min-h-screen max-w-xl flex-col gap-4 p-4">
      <div className="flex items-center gap-3">
        <div className="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <CameraIcon className="size-5" />
        </div>
        <div>
          <h1 className="font-semibold">{d?.name ?? '…'}</h1>
          <div className="text-xs text-muted">{[d?.branch, d?.location].filter(Boolean).join(' · ') || t('cst.subtitle')}</div>
        </div>
      </div>

      {on && (
        <div className="flex items-center gap-2 rounded-lg bg-danger/10 px-3 py-2 text-sm font-medium text-danger" role="status">
          <Circle className="size-3 animate-pulse fill-current" />
          {t('cst.live')}
        </div>
      )}
      {on && live && (
        <div className="flex items-center gap-2 rounded-lg bg-warning/10 px-3 py-2 text-sm font-medium text-warning" role="status">
          <Eye className="size-4" />
          {t('cst.watched')}
        </div>
      )}

      <Card className="overflow-hidden p-0">
        <video ref={video} playsInline muted className="aspect-video w-full bg-black object-cover" />
      </Card>

      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}

      {!on ? (
        <Button className="h-12 text-base" disabled={!d} onClick={() => void start()}>
          <CameraIcon className="size-5" />
          {t('cst.start')}
        </Button>
      ) : (
        <div className="flex gap-2">
          <Button
            variant="outline"
            className="h-12 flex-1"
            onClick={() => {
              const m = facing === 'user' ? 'environment' : 'user'
              setFacing(m)
              void start(m)
            }}
          >
            <SwitchCamera className="size-5" />
            {t('cst.switch')}
          </Button>
          <Button variant="danger" className="h-12 flex-1" onClick={() => void stop()}>
            <Square className="size-5" />
            {t('cst.stop')}
          </Button>
        </div>
      )}

      <p className="text-xs text-muted">{on ? t('cst.sending', { at: last ? last.toLocaleTimeString() : '…' }) : t('cst.notice')}</p>
      <p className="text-xs text-muted">{t('cst.keepOpen')}</p>
    </div>
  )
}
