import type { GeoJSONSource, Map as MapLibreMap, Marker } from 'maplibre-gl'
import { useEffect, useRef, useState } from 'react'

import { useMeta } from '../../features/meta/useMeta'

const DEFAULT_TILES = ['https://tile.openstreetmap.org/{z}/{x}/{y}.png']

/** Aylana (geofence) poligoni: markaz va radius (metr) bo'yicha. */
function circle(lat: number, lng: number, radius: number, steps = 64): [number, number][] {
  const out: [number, number][] = []
  const dLat = radius / 111_320
  const dLng = radius / (111_320 * Math.cos((lat * Math.PI) / 180))
  for (let i = 0; i <= steps; i++) {
    const a = (i / steps) * 2 * Math.PI
    out.push([lng + dLng * Math.cos(a), lat + dLat * Math.sin(a)])
  }
  return out
}

/**
 * Filial geozonasi xaritasi: filial nuqtasi, ruxsat etilgan radius (aylana) va xodimning joriy joylashuvi.
 * Xodim zonada bo'lsa aylana yashil, tashqarida bo'lsa qizil; ikkalasi ko'rinadigan qilib moslanadi.
 */
export function GeofenceMap({
  center,
  radius,
  me,
  inside,
  height = 240,
  recenterKey = 0,
}: {
  center: { lat: number; lng: number }
  radius: number
  me?: { lat: number; lng: number; accuracy: number } | null
  inside?: boolean
  height?: number
  /** O'zgarganda xarita qaytadan ikkala nuqtaga moslanadi */
  recenterKey?: number
}) {
  const el = useRef<HTMLDivElement>(null)
  const map = useRef<MapLibreMap | null>(null)
  const lib = useRef<typeof import('maplibre-gl') | null>(null)
  const meMarker = useRef<Marker | null>(null)
  const [ready, setReady] = useState(false)
  const fitted = useRef(false)
  const { data: meta } = useMeta()
  const tiles = meta?.map?.tiles ?? DEFAULT_TILES
  const attribution = meta?.map?.attribution ?? '© OpenStreetMap contributors'

  useEffect(() => {
    let cancelled = false
    void (async () => {
      const ml = await import('maplibre-gl')
      await import('maplibre-gl/dist/maplibre-gl.css')
      if (cancelled || !el.current) return
      lib.current = ml
      const m = new ml.Map({
        container: el.current,
        style: { version: 8, sources: { base: { type: 'raster', tiles, tileSize: 256, attribution } }, layers: [{ id: 'base', type: 'raster', source: 'base' }] },
        center: [center.lng, center.lat],
        zoom: 16,
        attributionControl: { compact: true },
      })
      m.addControl(new ml.NavigationControl({ showCompass: false }), 'top-right')
      const node = document.createElement('div')
      node.className = 'grid size-7 place-items-center rounded-full border-2 border-white bg-[var(--primary)] text-[11px] font-bold text-white shadow-lg'
      node.textContent = 'F'
      new ml.Marker({ element: node }).setLngLat([center.lng, center.lat]).addTo(m)
      m.on('load', () => {
        if (cancelled) return
        m.addSource('zone', { type: 'geojson', data: { type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [circle(center.lat, center.lng, radius)] } } })
        m.addLayer({ id: 'zone-fill', type: 'fill', source: 'zone', paint: { 'fill-color': '#16a34a', 'fill-opacity': 0.15 } })
        m.addLayer({ id: 'zone-line', type: 'line', source: 'zone', paint: { 'line-color': '#16a34a', 'line-width': 2, 'line-dasharray': [2, 2] } })
        m.addSource('link', { type: 'geojson', data: { type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: [] } } })
        m.addLayer({ id: 'link', type: 'line', source: 'link', paint: { 'line-color': '#e11d48', 'line-width': 2, 'line-dasharray': [1, 2] } })
        setReady(true)
      })
      map.current = m
    })()
    return () => {
      cancelled = true
      map.current?.remove()
      map.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [center.lat, center.lng, radius])

  // Zona rangi va xodim nuqtasi
  useEffect(() => {
    const m = map.current
    const ml = lib.current
    if (!m || !ml || !ready) return
    const color = inside === false ? '#e11d48' : '#16a34a'
    m.setPaintProperty('zone-fill', 'fill-color', color)
    m.setPaintProperty('zone-line', 'line-color', color)
    const link = m.getSource('link') as GeoJSONSource | undefined
    meMarker.current?.remove()
    meMarker.current = null
    if (!me) {
      link?.setData({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: [] } })
      return
    }
    const node = document.createElement('div')
    node.className = 'size-4 rounded-full border-[3px] border-white bg-blue-600 shadow-[0_0_0_6px_rgba(37,99,235,0.25)]'
    meMarker.current = new ml.Marker({ element: node }).setLngLat([me.lng, me.lat]).addTo(m)
    link?.setData({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: inside ? [] : [[me.lng, me.lat], [center.lng, center.lat]] } })
    if (!fitted.current) {
      fitted.current = true
      const b = new ml.LngLatBounds([center.lng, center.lat], [center.lng, center.lat]).extend([me.lng, me.lat])
      m.fitBounds(b, { padding: 56, maxZoom: 17, duration: 0 })
    }
  }, [me, inside, ready, center.lat, center.lng])

  // Qayta moslash (tugma bosilganda)
  useEffect(() => {
    if (!recenterKey) return
    fitted.current = false
    const m = map.current
    const ml = lib.current
    if (!m || !ml) return
    const b = new ml.LngLatBounds([center.lng, center.lat], [center.lng, center.lat])
    if (me) b.extend([me.lng, me.lat])
    m.fitBounds(b, { padding: 56, maxZoom: 17, duration: 300 })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recenterKey])

  return <div ref={el} style={{ height }} className="w-full overflow-hidden rounded-card border border-border" />
}
