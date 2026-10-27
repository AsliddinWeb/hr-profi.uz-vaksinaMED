/** Nisbiy o'zgarish %: (joriy − oldingi) / oldingi. Oldingi 0 yoki yo'q bo'lsa null. */
export function rel(cur: number, prev: number | null | undefined): number | null {
  if (prev === null || prev === undefined || prev === 0) return null
  return ((cur - prev) / prev) * 100
}

/** Foiz nuqtalardagi farq (nisbat ko'rsatkichlari uchun, masalan davomat foizi). */
export function pp(cur: number | null | undefined, prev: number | null | undefined): number | null {
  return cur === null || cur === undefined || prev === null || prev === undefined ? null : (cur - prev) * 100
}
