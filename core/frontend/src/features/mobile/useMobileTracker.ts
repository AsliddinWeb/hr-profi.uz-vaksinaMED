import { useEffect, useRef, useState } from 'react'

import { api } from '../../lib/api'

export interface Pt {
  lat: number
  lng: number
  accuracy: number | null
  speed: number | null
  heading: number | null
  at: string
}

export type TrackerState = 'waiting' | 'tracking' | 'denied' | 'unavailable' | 'offline' | 'closed'

interface Device {
  battery: number | null
  charging: boolean | null
  permission: 'granted' | 'denied' | 'prompt' | 'unknown'
  gps_enabled: boolean | null
}

interface BatteryManager {
  level: number
  charging: boolean
}

async function readDevice(gpsOk: boolean | null): Promise<Device> {
  let battery: number | null = null
  let charging: boolean | null = null
  try {
    const b = await (navigator as unknown as { getBattery?: () => Promise<BatteryManager> }).getBattery?.()
    if (b) {
      battery = Math.round(b.level * 100)
      charging = b.charging
    }
  } catch {
    /* Battery API yo'q */
  }
  let permission: Device['permission'] = 'unknown'
  if (gpsOk === true) permission = 'granted' // nuqta kelayotgan bo'lsa, ruxsat bor (Permissions API ba'zan "prompt" deydi)
  else {
    try {
      permission = (await navigator.permissions.query({ name: 'geolocation' })).state
    } catch {
      /* Permissions API yo'q */
    }
  }
  return { battery, charging, permission, gps_enabled: gpsOk }
}

/**
 * Ish kuni sessiyasi davomida joylashuvni kuzatadi va har `intervalS` soniyada (kamida 15) batch qilib yuboradi,
 * batareya va geolokatsiya ruxsati holatini qo'shib. Tarmoq yo'qolsa nuqtalar xotirada (2000 tagacha) saqlanadi.
 */
export function useMobileTracker(active: boolean, intervalS: number, onClosed: () => void) {
  const [state, setState] = useState<TrackerState>('waiting')
  const [last, setLast] = useState<Pt | null>(null)
  const [battery, setBattery] = useState<number | null>(null)
  const [sent, setSent] = useState(0)
  const [queued, setQueued] = useState(0)
  const queue = useRef<Pt[]>([])
  const gps = useRef<boolean | null>(null)
  const closedCb = useRef(onClosed)
  useEffect(() => {
    closedCb.current = onClosed
  })

  useEffect(() => {
    if (!active) return
    if (!navigator.geolocation) {
      queueMicrotask(() => setState('unavailable'))
      return
    }
    let stopped = false
    let lock: { release: () => Promise<void> } | null = null
    const flush = async () => {
      const d = await readDevice(gps.current)
      setBattery(d.battery)
      const batch = queue.current.slice(0, 100)
      try {
        const r = await api<{ saved: number }>('/api/v1/mobile/my/points', { method: 'POST', body: JSON.stringify({ points: batch, device: d }) })
        queue.current = queue.current.slice(batch.length)
        setSent((n) => n + r.saved)
        setQueued(queue.current.length)
        setState((s) => (s === 'offline' ? 'tracking' : s))
        if (queue.current.length > 0 && !stopped) void flush()
      } catch (e) {
        const code = (e as { code?: string }).code
        if (code === 'session_closed' || code === 'no_session') {
          stopped = true
          setState('closed')
          closedCb.current()
        } else setState('offline')
      }
    }
    let firstFix = true
    const watch = navigator.geolocation.watchPosition(
      (pos) => {
        gps.current = true
        if (firstFix) {
          firstFix = false
          window.setTimeout(() => void flush(), 2000) // birinchi nuqta darhol ko'rinsin
        }
        const p: Pt = { lat: pos.coords.latitude, lng: pos.coords.longitude, accuracy: pos.coords.accuracy, speed: pos.coords.speed !== null && pos.coords.speed >= 0 ? Math.round(pos.coords.speed * 3.6 * 10) / 10 : null, heading: pos.coords.heading !== null && !Number.isNaN(pos.coords.heading) ? pos.coords.heading : null, at: new Date(pos.timestamp).toISOString() }
        queue.current = [...queue.current, p].slice(-2000)
        setQueued(queue.current.length)
        setLast(p)
        setState((s) => (s === 'offline' || s === 'closed' ? s : 'tracking'))
      },
      (e) => {
        gps.current = e.code === e.PERMISSION_DENIED ? null : false
        setState(e.code === e.PERMISSION_DENIED ? 'denied' : 'unavailable')
      },
      { enableHighAccuracy: true, maximumAge: Math.max(intervalS, 15) * 500, timeout: 30_000 },
    )
    const timer = window.setInterval(() => void flush(), Math.max(intervalS, 15) * 1000)
    const wl = (navigator as unknown as { wakeLock?: { request: (t: 'screen') => Promise<{ release: () => Promise<void> }> } }).wakeLock
    void wl?.request('screen').then((l) => (lock = l)).catch(() => undefined)
    void flush()
    return () => {
      stopped = true
      navigator.geolocation.clearWatch(watch)
      window.clearInterval(timer)
      void lock?.release()
    }
  }, [active, intervalS])

  return { state: active ? state : 'waiting', last, battery, sent, queued }
}
