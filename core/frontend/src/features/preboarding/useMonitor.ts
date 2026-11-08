import type { Room } from 'livekit-client'
import { useEffect, useRef, useState } from 'react'

import { upload } from '../../lib/api'
import { livekitUrl, type LiveToken, type Monitoring } from './api'

const CLIP_MS = 60_000
const SNAP_MS = 30_000

function recorderMime(): string | undefined {
  if (typeof MediaRecorder === 'undefined') return undefined
  return ['video/webm;codecs=vp8,opus', 'video/webm', 'video/mp4'].find((m) => MediaRecorder.isTypeSupported(m))
}

export interface MonitorState {
  stream: MediaStream | null
  cameraOk: boolean
  error: 'denied' | 'unavailable' | null
  recording: boolean
  live: boolean
  /** Keyingi tick bilan yuboriladigan hodisa (kamera o'chdi, oyna yashirildi) */
  takeEvent: () => string | null
}

/**
 * Dars paytidagi kamera + mikrofon nazorati: ~60 s lik yozuv bo'laklari, har 30 s surat, jonli efir (LiveKit).
 * `monitorId` bo'lmasa (kamera talab qilinmaydi) hech narsa qilmaydi.
 */
export function useMonitor(monitorId: number | null, mon: Monitoring, live: LiveToken | null): MonitorState {
  const [stream, setStream] = useState<MediaStream | null>(null)
  const [cameraOk, setCameraOk] = useState(false)
  const [error, setError] = useState<'denied' | 'unavailable' | null>(null)
  const [isLive, setIsLive] = useState(false)
  const pending = useRef<string | null>(null)

  // Kamera va mikrofon
  useEffect(() => {
    if (!monitorId || !mon.camera) return
    let s: MediaStream | null = null
    let alive = true
    navigator.mediaDevices
      ?.getUserMedia({ video: { width: 320, height: 240, frameRate: 15, facingMode: 'user' }, audio: true })
      .then((st) => {
        if (!alive) return st.getTracks().forEach((tr) => tr.stop())
        s = st
        setStream(st)
        setCameraOk(true)
        st.getTracks().forEach((tr) => {
          tr.onended = () => {
            setCameraOk(false)
            pending.current = tr.kind === 'video' ? 'camera_off' : 'mic_off'
          }
          tr.onmute = () => (pending.current = tr.kind === 'video' ? 'camera_muted' : 'mic_muted')
        })
      })
      .catch((e: DOMException) => setError(e?.name === 'NotAllowedError' ? 'denied' : 'unavailable'))
    const vis = () => {
      if (document.visibilityState === 'hidden') pending.current = 'hidden'
    }
    document.addEventListener('visibilitychange', vis)
    return () => {
      alive = false
      document.removeEventListener('visibilitychange', vis)
      s?.getTracks().forEach((tr) => tr.stop())
      setStream(null)
      setCameraOk(false)
      void fetch(`/api/v1/preboarding/my/monitor/${monitorId}/end`, { method: 'POST', keepalive: true, credentials: 'include', headers: { 'X-Requested-With': 'fetch' } })
    }
  }, [monitorId, mon.camera])

  // Yozib olish: har ~60 s mustaqil fayl (to'xtatib qayta boshlanadi)
  const mime = recorderMime()
  useEffect(() => {
    if (!stream || !monitorId || !mon.record || !mime) return
    let stopped = false
    let rec: MediaRecorder | null = null
    let timer = 0
    const cycle = () => {
      if (stopped) return
      const chunks: Blob[] = []
      rec = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 250_000, audioBitsPerSecond: 32_000 })
      rec.ondataavailable = (e) => e.data.size && chunks.push(e.data)
      rec.onstop = () => {
        const blob = new Blob(chunks, { type: mime.split(';')[0] })
        if (blob.size > 1000) {
          const fd = new FormData()
          fd.append('file', blob, mime.includes('mp4') ? 'clip.mp4' : 'clip.webm')
          void upload('POST', `/api/v1/preboarding/my/monitor/${monitorId}/clip`, fd).catch(() => undefined)
        }
        cycle()
      }
      rec.start()
      timer = window.setTimeout(() => rec?.state === 'recording' && rec.stop(), CLIP_MS)
    }
    cycle()
    return () => {
      stopped = true
      window.clearTimeout(timer)
      if (rec?.state === 'recording') rec.stop()
    }
  }, [stream, monitorId, mon.record, mime])

  // Suratlar
  useEffect(() => {
    if (!stream || !monitorId || !mon.snapshots) return
    const video = document.createElement('video')
    video.muted = true
    video.playsInline = true
    video.srcObject = stream
    void video.play().catch(() => undefined)
    const canvas = document.createElement('canvas')
    canvas.width = 320
    canvas.height = 240
    const shoot = () => {
      if (!video.videoWidth) return
      canvas.getContext('2d')?.drawImage(video, 0, 0, 320, 240)
      canvas.toBlob(
        (b) => {
          if (!b) return
          const fd = new FormData()
          fd.append('file', b, 'snap.jpg')
          void upload('POST', `/api/v1/preboarding/my/monitor/${monitorId}/snapshot`, fd).catch(() => undefined)
        },
        'image/jpeg',
        0.7,
      )
    }
    const first = window.setTimeout(shoot, 3000)
    const id = window.setInterval(shoot, SNAP_MS)
    return () => {
      window.clearTimeout(first)
      window.clearInterval(id)
      video.srcObject = null
    }
  }, [stream, monitorId, mon.snapshots])

  // Jonli efir: faqat nashr qiladi (HR yashirin tomoshabin)
  useEffect(() => {
    if (!stream || !live) return
    let room: Room | null = null
    let alive = true
    void (async () => {
      try {
        const mod = await import('livekit-client')
        room = new mod.Room()
        await room.connect(livekitUrl(live), live.token)
        if (!alive) return void room.disconnect()
        for (const tr of stream.getTracks()) await room.localParticipant.publishTrack(tr)
        setIsLive(true)
      } catch {
        setIsLive(false)
      }
    })()
    return () => {
      alive = false
      setIsLive(false)
      void room?.disconnect()
    }
  }, [stream, live])

  return {
    stream,
    cameraOk: !mon.camera || cameraOk,
    error,
    recording: !!(stream && mon.record && mime),
    live: isLive,
    takeEvent: () => {
      const e = pending.current
      pending.current = null
      return e
    },
  }
}
