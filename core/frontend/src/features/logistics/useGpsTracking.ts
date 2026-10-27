import { useEffect, useRef, useState } from 'react'

import { send } from '../../lib/api'

export interface TrackPoint {
  lat: number
  lng: number
  speed: number | null
  accuracy: number | null
  heading: number | null
  at: string
}

export type TrackState = 'waiting' | 'tracking' | 'denied' | 'unavailable' | 'error'

const FLUSH_MS = 15_000
const MAX_QUEUE = 2000

/**
 * Faol reys davomida joylashuvni kuzatadi va har 15 soniyada serverga yuboradi. Tarmoq yo'q bo'lsa nuqtalar
 * xotirada (2000 tagacha) saqlanib, ulanish tiklangach yuboriladi. Ekran o'chmasligi uchun Wake Lock so'raladi (qo'llab-quvvatlansa).
 */
export function useGpsTracking(active: boolean) {
  const [state, setState] = useState<TrackState>('waiting')
  const [last, setLast] = useState<TrackPoint | null>(null)
  const [sent, setSent] = useState(0)
  const [queued, setQueued] = useState(0)
  const queue = useRef<TrackPoint[]>([])

  useEffect(() => {
    if (!active) return
    if (!navigator.geolocation) {
      queueMicrotask(() => setState('unavailable'))
      return
    }
    let stopped = false
    let lock: { release: () => Promise<void> } | null = null
    const flush = async () => {
      while (queue.current.length > 0 && !stopped) {
        const batch = queue.current.slice(0, 100)
        try {
          const r = await send<{ saved: number }>('POST', '/api/v1/logistics/track', { points: batch })
          queue.current = queue.current.slice(batch.length)
          setSent((n) => n + r.saved)
          setQueued(queue.current.length)
          setState((s) => (s === 'error' ? 'tracking' : s))
        } catch {
          setState('error')
          return
        }
      }
    }
    const watch = navigator.geolocation.watchPosition(
      (pos) => {
        const p: TrackPoint = {
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          speed: pos.coords.speed !== null && pos.coords.speed >= 0 ? Math.round(pos.coords.speed * 3.6 * 10) / 10 : null,
          accuracy: pos.coords.accuracy,
          heading: pos.coords.heading !== null && !Number.isNaN(pos.coords.heading) ? pos.coords.heading : null,
          at: new Date(pos.timestamp).toISOString(),
        }
        queue.current = [...queue.current, p].slice(-MAX_QUEUE)
        setQueued(queue.current.length)
        setLast(p)
        setState((s) => (s === 'error' ? s : 'tracking'))
      },
      (e) => setState(e.code === e.PERMISSION_DENIED ? 'denied' : 'unavailable'),
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 30_000 },
    )
    const timer = window.setInterval(() => void flush(), FLUSH_MS)
    const wl = (navigator as unknown as { wakeLock?: { request: (t: 'screen') => Promise<{ release: () => Promise<void> }> } }).wakeLock
    void wl?.request('screen').then((l) => (lock = l)).catch(() => undefined)
    return () => {
      stopped = true
      navigator.geolocation.clearWatch(watch)
      window.clearInterval(timer)
      void lock?.release()
    }
  }, [active])

  return { state: active ? state : 'waiting', last, sent, queued }
}
