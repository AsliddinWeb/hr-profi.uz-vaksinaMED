import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'

import { api } from '../../lib/api'

export interface Meta {
  version: string
  client: string
  brand: { name: string; tagline: string; primary: string; accent: string; logo: string | null }
  modules: string[]
  extension: boolean
  map?: { tiles?: string[]; attribution?: string } | null
}

/** Rang ustidagi matn rangi: yorug'ligiga qarab oq yoki qora. */
function readable(hexColor: string): string {
  const n = parseInt(hexColor.slice(1), 16)
  const lum = (0.299 * ((n >> 16) & 255) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255)) / 255
  return lum > 0.62 ? '#141414' : '#ffffff'
}

export function useMeta() {
  const query = useQuery({ queryKey: ['meta'], queryFn: () => api<Meta>('/api/v1/meta'), staleTime: 5 * 60_000 })
  const brand = query.data?.brand

  // Mijoz brendini (rang, sarlavha) runtime'da qo'llaymiz
  useEffect(() => {
    if (!brand) return
    const root = document.documentElement.style
    const hex = /^#[0-9a-f]{6}$/i
    // Standart HR-Profi ko'k (#0b5ed7) bo'lsa mavzu o'zi ishlaydi; boshqa brend rangi bo'lsa qo'llanadi (dark da yorqinlashtiriladi)
    if (hex.test(brand.primary) && brand.primary.toLowerCase() !== '#0b5ed7') {
      root.setProperty('--brand', brand.primary)
      root.setProperty('--brand-fg', readable(brand.primary))
      root.setProperty('--brand-dark', `color-mix(in oklab, ${brand.primary} 62%, white)`)
      root.setProperty('--brand-dark-fg', '#141414')
    }
    if (hex.test(brand.accent)) root.setProperty('--accent', brand.accent)
    document.title = brand.name
  }, [brand])

  return query
}
