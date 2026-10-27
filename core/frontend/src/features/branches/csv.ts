/** Filiallar CSV importi (mijoz tomonida). Vergul, nuqta-vergul yoki tab ajratgich. */

export interface BranchCsvRow {
  number?: number
  name?: string
  address?: string
  district?: string
  phone?: string
  latitude?: number
  longitude?: number
  geofence_radius_m?: number
}

const ALIASES: Record<keyof BranchCsvRow, string[]> = {
  number: ['number', 'raqam', '№', 'no', 'nomer', 'номер'],
  name: ['name', 'nom', 'nomi', 'название', 'filial'],
  address: ['address', 'manzil', 'адрес'],
  district: ['district', 'tuman', 'район'],
  phone: ['phone', 'telefon', 'tel', 'телефон'],
  latitude: ['latitude', 'lat', 'kenglik', 'широта'],
  longitude: ['longitude', 'lng', 'lon', 'uzunlik', 'долгота'],
  geofence_radius_m: ['radius', 'geofence_radius_m', 'radius_m'],
}

function detectDelimiter(line: string): string {
  const counts = { '\t': 0, ';': 0, ',': 0 }
  let quoted = false
  for (const ch of line) {
    if (ch === '"') quoted = !quoted
    else if (!quoted && ch in counts) counts[ch as keyof typeof counts]++
  }
  return (Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] as string) || ','
}

export function splitLine(line: string, delimiter: string): string[] {
  const out: string[] = []
  let cur = ''
  let quoted = false
  for (let i = 0; i < line.length; i++) {
    const ch = line[i]
    if (quoted) {
      if (ch === '"' && line[i + 1] === '"') {
        cur += '"'
        i++
      } else if (ch === '"') quoted = false
      else cur += ch
    } else if (ch === '"') quoted = true
    else if (ch === delimiter) {
      out.push(cur)
      cur = ''
    } else cur += ch
  }
  out.push(cur)
  return out.map((c) => c.trim())
}

const toNumber = (v: string): number | undefined => {
  if (!v) return undefined
  const n = Number(v.replace(',', '.').replace(/\s/g, ''))
  return Number.isFinite(n) ? n : NaN
}

/** Birinchi qator sarlavha bo'lishi shart. Noma'lum ustunlar e'tiborsiz qoldiriladi. */
export function parseBranchCsv(text: string): { rows: BranchCsvRow[]; unknownColumns: string[] } {
  const lines = text.replace(/^﻿/, '').split(/\r?\n/).filter((l) => l.trim())
  if (lines.length < 2) return { rows: [], unknownColumns: [] }
  const delimiter = detectDelimiter(lines[0])
  const headers = splitLine(lines[0], delimiter).map((h) => h.toLowerCase().replace(/^№$/, '№'))

  const map: (keyof BranchCsvRow | null)[] = headers.map(
    (h) => (Object.keys(ALIASES) as (keyof BranchCsvRow)[]).find((k) => ALIASES[k].includes(h)) ?? null,
  )
  const unknownColumns = headers.filter((_, i) => map[i] === null)

  const rows = lines.slice(1).map((line) => {
    const cells = splitLine(line, delimiter)
    const row: BranchCsvRow = {}
    map.forEach((key, i) => {
      const v = cells[i] ?? ''
      if (!key || v === '') return
      if (key === 'number' || key === 'geofence_radius_m') {
        const n = toNumber(v)
        // JSON da NaN bo'lmaydi: yaroqsiz raqamni backend rad etadigan qiymatga (0) aylantiramiz
        ;(row as Record<string, unknown>)[key] = Number.isNaN(n) ? 0 : n
      } else if (key === 'latitude' || key === 'longitude') {
        const n = toNumber(v)
        ;(row as Record<string, unknown>)[key] = Number.isNaN(n) ? 999 : n
      } else {
        ;(row as Record<string, unknown>)[key] = v
      }
    })
    return row
  })
  return { rows, unknownColumns }
}
