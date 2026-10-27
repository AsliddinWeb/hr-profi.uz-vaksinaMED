import { describe, expect, it } from 'vitest'

import { initials, relativeTime } from './format'

const ago = (s: number) => new Date(Date.now() - s * 1000).toISOString()

describe('format', () => {
  it('relativeTime uz', () => {
    expect(relativeTime(ago(5), 'uz')).toBe('hozir')
    expect(relativeTime(ago(5 * 60), 'uz')).toBe('5 daqiqa oldin')
    expect(relativeTime(ago(3 * 3600), 'uz')).toBe('3 soat oldin')
    expect(relativeTime(ago(2 * 86400), 'uz')).toBe('2 kun oldin')
  })
  it('relativeTime ru', () => {
    expect(relativeTime(ago(5), 'ru')).toBe('только что')
  })
  it('initials', () => {
    expect(initials('Tursunboyev Orifjon')).toBe('TO')
    expect(initials('  ali ')).toBe('A')
  })
})

describe('sana formatlari', () => {
  it('KK.OO.YYYY', async () => {
    const { formatDate } = await import('./format')
    expect(formatDate('2026-10-22', 'uz')).toBe('22.10.2026')
    expect(formatDate(null, 'uz')).toBe('—')
  })
})
