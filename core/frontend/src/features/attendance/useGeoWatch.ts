import { useEffect, useState } from 'react'

import type { Position } from './geo'

export type GeoState =
  | { status: 'idle' | 'locating' }
  | { status: 'denied' | 'unavailable' }
  | { status: 'ok'; pos: Position; at: number }

/** Joylashuvni jonli kuzatadi (sahifa ochiq turganda). Ruxsat yo'q yoki GPS o'chiq bo'lsa holati shuni ko'rsatadi. */
export function useGeoWatch(enabled: boolean): GeoState {
  const supported = typeof navigator !== 'undefined' && !!navigator.geolocation
  const [state, setState] = useState<GeoState>({ status: 'locating' })
  useEffect(() => {
    if (!enabled || !supported) return
    const id = navigator.geolocation.watchPosition(
      (p) => setState({ status: 'ok', pos: { lat: p.coords.latitude, lng: p.coords.longitude, accuracy: p.coords.accuracy }, at: Date.now() }),
      (e) => setState({ status: e.code === e.PERMISSION_DENIED ? 'denied' : 'unavailable' }),
      { enableHighAccuracy: true, timeout: 20_000, maximumAge: 10_000 },
    )
    return () => navigator.geolocation.clearWatch(id)
  }, [enabled, supported])
  if (!enabled) return { status: 'idle' }
  if (!supported) return { status: 'unavailable' }
  return state
}

export const qrSupported = () => typeof window !== 'undefined' && 'BarcodeDetector' in window

/** Ikki nuqta orasidagi masofa, metr (serverdagi haversine bilan bir xil formula). */
export function distanceM(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  const R = 6_371_000
  const rad = (d: number) => (d * Math.PI) / 180
  const dLat = rad(b.lat - a.lat)
  const dLng = rad(b.lng - a.lng)
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(h))
}

export function fmtDistance(m: number): string {
  return m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`
}
