import { describe, expect, it } from 'vitest'

import { fmtDuration, monthRange, shiftMonth } from './api'

describe('schedule helpers', () => {
  it('formats duration', () => {
    expect(fmtDuration(540)).toBe('9')
    expect(fmtDuration(1440)).toBe('24')
    expect(fmtDuration(510)).toBe('8:30')
  })
  it('computes month range incl. leap February', () => {
    expect(monthRange('2026-02')).toEqual({ start: '2026-02-01', end: '2026-02-28' })
    expect(monthRange('2028-02').end).toBe('2028-02-29')
  })
  it('shifts months across year boundary', () => {
    expect(shiftMonth('2026-12', 1)).toBe('2027-01')
    expect(shiftMonth('2026-01', -1)).toBe('2025-12')
  })
})
