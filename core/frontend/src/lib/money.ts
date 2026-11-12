/** Pul summalari: formulali hisoblash va xonalarga bo'lib ko'rsatish. */

const WORDS: Record<string, number> = { mlrd: 1e9, milliard: 1e9, mln: 1e6, million: 1e6, ming: 1e3, k: 1e3, тыс: 1e3, млн: 1e6, млрд: 1e9 }

/** Pul ifodasini hisoblaydi: + - * / ( ), "8 mln", "500 ming", "1,5 mln", probelli sonlar. eval ishlatilmaydi. Noto'g'ri bo'lsa null. */
export function calcMoney(src: string): number | null {
  let s = src.toLowerCase().replace(/so'?m|сум/g, '').replace(/[×x]/g, '*').replace(/÷/g, '/').replace(/(\d)[\s ](?=\d{3}\b)/g, '$1').replace(/(\d),(\d)/g, '$1.$2')
  for (const [w, v] of Object.entries(WORDS)) s = s.replace(new RegExp(`(\\d+(?:\\.\\d+)?)\\s*${w}\\b`, 'g'), (_, n) => String(Number(n) * v))
  s = s.replace(/\s+/g, '')
  if (!s || /[^0-9.+\-*/()]/.test(s)) return null
  let i = 0
  const peek = () => s[i]
  const num = (): number => {
    if (peek() === '(') {
      i++
      const v = expr()
      if (peek() !== ')') throw new Error('paren')
      i++
      return v
    }
    if (peek() === '-') {
      i++
      return -num()
    }
    const m = /^\d+(\.\d+)?/.exec(s.slice(i))
    if (!m) throw new Error('num')
    i += m[0].length
    return Number(m[0])
  }
  const term = (): number => {
    let v = num()
    while (peek() === '*' || peek() === '/') {
      const op = s[i++]
      const r = num()
      v = op === '*' ? v * r : v / r
    }
    return v
  }
  const expr = (): number => {
    let v = term()
    while (peek() === '+' || peek() === '-') {
      const op = s[i++]
      const r = term()
      v = op === '+' ? v + r : v - r
    }
    return v
  }
  try {
    const v = expr()
    return i === s.length && Number.isFinite(v) ? Math.round(v) : null
  } catch {
    return null
  }
}

export const fmtMoney = (n: number) => n.toLocaleString('ru-RU').replace(/ /g, ' ')
