import { describe, expect, it } from 'vitest'

import { parseBranchCsv, splitLine } from './csv'

describe('parseBranchCsv', () => {
  it('vergul, sarlavha aliaslari va koordinatalar', () => {
    const { rows, unknownColumns } = parseBranchCsv('№,Nomi,Tuman,lat,lng,izoh\n16,1-gor bolnitsa,Yunusobod,41.36,69.28,x\n')
    expect(rows).toEqual([{ number: 16, name: '1-gor bolnitsa', district: 'Yunusobod', latitude: 41.36, longitude: 69.28 }])
    expect(unknownColumns).toEqual(['izoh'])
  })

  it("nuqta-vergul va o'nlik vergul (Excel)", () => {
    const { rows } = parseBranchCsv('raqam;nom;lat;lng\n7;Test;41,3111;69,2797')
    expect(rows[0]).toMatchObject({ number: 7, name: 'Test', latitude: 41.3111, longitude: 69.2797 })
  })

  it('tab bilan ajratilgan (Excelдан nusxa) va qo\'shtirnoq', () => {
    const { rows } = parseBranchCsv('number\tname\taddress\n1\t"A, B ""C"""\tKo\'cha 5')
    expect(rows[0]).toEqual({ number: 1, name: 'A, B "C"', address: "Ko'cha 5" })
  })

  it("bo'sh kataklar o'tkazib yuboriladi, sarlavhasiz fayl bo'sh", () => {
    expect(parseBranchCsv('name,phone\nA,\n').rows).toEqual([{ name: 'A' }])
    expect(parseBranchCsv('faqat bir qator').rows).toEqual([])
  })

  it("noto'g'ri raqamlar backend rad etadigan qiymatga aylanadi", () => {
    const { rows } = parseBranchCsv('number,name,lat,lng\nabc,X,qq,10')
    expect(rows[0].number).toBe(0)
    expect(rows[0].latitude).toBe(999)
  })

  it('splitLine', () => {
    expect(splitLine('a,"b,c",d', ',')).toEqual(['a', 'b,c', 'd'])
  })
})
