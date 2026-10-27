import { describe, expect, it } from 'vitest'

import { addDays, fmtMin, fromLocalInput, mondayOf, toLocalInput } from './api'

describe('attendance helpers', () => {
  it('formats minutes', () => {
    expect(fmtMin(485)).toBe('8:05')
    expect(fmtMin(0)).toBe('0:00')
  })
  it('round-trips Tashkent local input', () => {
    const iso = fromLocalInput('2026-11-02T09:25')
    expect(iso).toBe('2026-11-02T09:25:00+05:00')
    expect(toLocalInput(iso)).toBe('2026-11-02T09:25')
    expect(toLocalInput('2026-11-02T20:30:00Z')).toBe('2026-11-03T01:30')
    expect(fromLocalInput('')).toBeNull()
  })
  it('computes week boundaries', () => {
    expect(mondayOf('2026-11-04')).toBe('2026-11-02')
    expect(mondayOf('2026-11-08')).toBe('2026-11-02')
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01')
  })
})
