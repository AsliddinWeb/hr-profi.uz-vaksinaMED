import { describe, expect, it } from 'vitest'

import { calcMoney, fmtMoney } from './money'

describe('calcMoney', () => {
  it('sonlar va formulalar', () => {
    expect(calcMoney('10 000 000')).toBe(10_000_000)
    expect(calcMoney('5000000*2')).toBe(10_000_000)
    expect(calcMoney('8 mln + 500 ming')).toBe(8_500_000)
    expect(calcMoney('1,5 mln')).toBe(1_500_000)
    expect(calcMoney('(3+2)*1000000')).toBe(5_000_000)
    expect(calcMoney('12000000/12')).toBe(1_000_000)
    expect(calcMoney("7 mln so'm")).toBe(7_000_000)
    expect(calcMoney('abc')).toBeNull()
    expect(calcMoney('2*(3')).toBeNull()
  })
  it('format', () => expect(fmtMoney(15000000)).toBe('15 000 000'))
})
