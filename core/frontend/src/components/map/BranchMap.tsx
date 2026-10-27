import type { GeoJSONSource, Map as MapLibreMap, Marker } from 'maplibre-gl'
import { useEffect, useRef, useState } from 'react'

import { useMeta } from '../../features/meta/useMeta'

export interface MapPoint {
  id: number
  lat: number
  lng: number
  label: string
  popup?: string
  inactive?: boolean
  /** Belgi rangi (masalan holat bo'yicha); berilmasa brend rangi */
  color?: string
}

const DEFAULT_TILES = ['https://tile.openstreetmap.org/{z}/{x}/{y}.png']
const TASHKENT: [number, number] = [69.2797, 41.3111]

/**
 * MapLibre xaritasi (lazy yuklanadi). `points` - belgilar; `onPick` berilsa xaritani bosib nuqta tanlanadi;
 * `picked` - tanlangan nuqta (surish mumkin). Tile manbasi mijoz sozlamasidan (`settings.map.tiles`).
 */
export function BranchMap({
  points = [],
  picked,
  onPick,
  onSelect,
  path,
  fit = true,
  height = 420,
}: {
  points?: MapPoint[]
  picked?: { lat: number; lng: number } | null
  onPick?: (p: { lat: number; lng: number }) => void
  /** Belgi bosilganda (id bilan) */
  onSelect?: (id: number) => void
  /** Chiziq (masalan reys treki) */
  path?: { lat: number; lng: number }[]
  /** Belgilar o'zgarganda xaritani ularga moslash (jonli xaritada o'chiriladi) */
  fit?: boolean
  height?: number
}) {
  const el = useRef<HTMLDivElement>(null)
  const map = useRef<MapLibreMap | null>(null)
  const markers = useRef<Marker[]>([])
  const pickMarker = useRef<Marker | null>(null)
  const lib = useRef<typeof import('maplibre-gl') | null>(null)
  const [ready, setReady] = useState(false)
  const onPickRef = useRef(onPick)
  const onSelectRef = useRef(onSelect)
  const { data: meta } = useMeta()
  const tiles = meta?.map?.tiles ?? DEFAULT_TILES
  const attribution = meta?.map?.attribution ?? '© OpenStreetMap contributors'

  useEffect(() => {
    onPickRef.current = onPick
    onSelectRef.current = onSelect
  })

  // Xaritani yaratish (bir marta)
  useEffect(() => {
    let cancelled = false
    void (async () => {
      const ml = await import('maplibre-gl')
      await import('maplibre-gl/dist/maplibre-gl.css')
      if (cancelled || !el.current) return
      lib.current = ml
      const m = new ml.Map({
        container: el.current,
        style: {
          version: 8,
          sources: { base: { type: 'raster', tiles, tileSize: 256, attribution } },
          layers: [{ id: 'base', type: 'raster', source: 'base' }],
        },
        center: TASHKENT,
        zoom: 10,
        attributionControl: { compact: true },
      })
      m.addControl(new ml.NavigationControl({ showCompass: false }), 'top-right')
      m.on('click', (e) => onPickRef.current?.({ lat: e.lngLat.lat, lng: e.lngLat.lng }))
      map.current = m
      setReady(true)
    })()
    return () => {
      cancelled = true
      map.current?.remove()
      map.current = null
      setReady(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Belgilar
  useEffect(() => {
    const draw = () => {
      const m = map.current
      const ml = lib.current
      if (!m || !ml) return
      markers.current.forEach((x) => x.remove())
      markers.current = points.map((p) => {
        const node = document.createElement('div')
        node.className = 'size-3.5 rounded-full border-2 border-white shadow'
        node.style.background = p.color ?? (p.inactive ? '#9ca3af' : 'var(--primary)')
        node.title = p.label
        node.style.cursor = onSelectRef.current ? 'pointer' : ''
        node.addEventListener('click', (ev) => {
          if (onSelectRef.current) {
            ev.stopPropagation()
            onSelectRef.current(p.id)
          }
        })
        const marker = new ml.Marker({ element: node }).setLngLat([p.lng, p.lat])
        if (p.popup) marker.setPopup(new ml.Popup({ offset: 12 }).setText(p.popup))
        return marker.addTo(m)
      })
      if (points.length && !picked && fit) {
        const b = new ml.LngLatBounds()
        points.forEach((p) => b.extend([p.lng, p.lat]))
        m.fitBounds(b, { padding: 48, maxZoom: 14, duration: 0 })
      }
    }
    draw()
  }, [points, picked, ready, fit])

  // Chiziq
  useEffect(() => {
    const m = map.current
    if (!m) return
    const apply = () => {
      const data = { type: 'Feature' as const, properties: {}, geometry: { type: 'LineString' as const, coordinates: (path ?? []).map((p) => [p.lng, p.lat]) } }
      const src = m.getSource('path') as GeoJSONSource | undefined
      if (src) src.setData(data)
      else {
        m.addSource('path', { type: 'geojson', data })
        m.addLayer({ id: 'path', type: 'line', source: 'path', paint: { 'line-color': '#2563eb', 'line-width': 4 } })
      }
      if (path && path.length > 1 && lib.current) {
        const b = new lib.current.LngLatBounds()
        path.forEach((p) => b.extend([p.lng, p.lat]))
        m.fitBounds(b, { padding: 48, maxZoom: 16, duration: 0 })
      }
    }
    if (m.isStyleLoaded()) apply()
    else m.once('load', apply)
  }, [path, ready])

  // Tanlangan nuqta
  useEffect(() => {
    const place = () => {
      const m = map.current
      const ml = lib.current
      if (!m || !ml) return
      pickMarker.current?.remove()
      pickMarker.current = null
      if (picked) {
        pickMarker.current = new ml.Marker({ color: '#e11d48', draggable: !!onPickRef.current })
          .setLngLat([picked.lng, picked.lat])
          .addTo(m)
        pickMarker.current.on('dragend', () => {
          const ll = pickMarker.current?.getLngLat()
          if (ll) onPickRef.current?.({ lat: ll.lat, lng: ll.lng })
        })
        m.easeTo({ center: [picked.lng, picked.lat], zoom: Math.max(m.getZoom(), 15), duration: 300 })
      }
    }
    place()
  }, [picked, ready])

  return <div ref={el} style={{ height }} className="w-full overflow-hidden rounded-card border border-border" />
}
