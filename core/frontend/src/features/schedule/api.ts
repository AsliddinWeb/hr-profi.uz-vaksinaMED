export interface Shift {
  id: number
  name: string
  code: string | null
  kind: 'fixed' | 'flexible'
  start_time: string
  end_time: string
  overnight: boolean
  duration_minutes: number
  break_minutes: number
  late_grace_minutes: number
  early_leave_grace_minutes: number
  min_work_minutes: number | null
  track_lateness: boolean
  color: string | null
  sort_order: number
  is_active: boolean
}

export const CATEGORIES = ['office', 'pharmacy', 'warehouse', 'security', 'other'] as const
export type Category = (typeof CATEGORIES)[number]

export interface WorkGroup {
  id: number
  name: string
  category: Category
  description: string | null
  default_shift_id: number | null
  default_shift_name: string | null
  weekly_off_days: number[]
  observe_holidays: boolean
  attendance_required: boolean
  is_default: boolean
  sort_order: number
  is_active: boolean
  members: number
}

export interface Pattern {
  id: number
  name: string
  description: string | null
  cycle: { shift_id: number | null }[]
  length: number
  work_days: number
  is_active: boolean
}

export interface Holiday {
  id: number
  name: string
  kind: 'holiday' | 'workday'
  yearly: boolean
  year: number | null
  month: number
  day: number
  date: string
  note: string | null
}

export interface Cell {
  working: boolean
  shift_id: number | null
  reason: 'entry' | 'entry_off' | 'holiday' | 'weekly_off' | 'default' | 'no_shift' | 'no_group'
  explicit: boolean
  holiday: string | null
}

export interface BoardDay {
  date: string
  weekday: number
  holiday: { name: string; kind: 'holiday' | 'workday' } | null
}

export interface Board {
  total: number
  page: number
  size: number
  days: BoardDay[]
  shifts: Record<string, Shift>
  rows: {
    employee: { id: number; employee_no: number; full_name: string; position: string | null; group: string | null }
    cells: Cell[]
  }[]
}

export interface EmployeeMonth {
  employee: { id: number; employee_no: number; full_name: string; status: string }
  group: { id: number; name: string; attendance_required: boolean } | null
  shifts: Record<string, Shift>
  days: (Cell & { date: string; weekday: number })[]
}

export interface ApplyResult {
  employees: number
  to_create: number
  to_update: number
  to_delete: number
  skipped: number
  applied: boolean
}

/** Qat'iy (har yili bir sanadagi) bayramlar: backend `FIXED_HOLIDAYS_UZ` bilan mos. */
export const FIXED_HOLIDAYS = [
  ['01-01', 'Yangi yil'],
  ['03-08', 'Xalqaro xotin-qizlar kuni'],
  ['03-21', "Navro'z bayrami"],
  ['05-09', 'Xotira va qadrlash kuni'],
  ['09-01', 'Mustaqillik kuni'],
  ['10-01', "O'qituvchi va murabbiylar kuni"],
  ['12-08', 'Konstitutsiya kuni'],
] as const

const PALETTE = ['#2563eb', '#16a34a', '#d97706', '#9333ea', '#0891b2', '#dc2626', '#4f46e5', '#0d9488']
export const SHIFT_COLORS = PALETTE

export const shiftColor = (s: Pick<Shift, 'id' | 'color'>) => s.color ?? PALETTE[s.id % PALETTE.length]!
export const shiftLabel = (s: Pick<Shift, 'name' | 'code'>) => s.code || s.name.slice(0, 2).toUpperCase()

export function fmtDuration(min: number): string {
  const h = Math.floor(min / 60)
  const m = min % 60
  return m ? `${h}:${String(m).padStart(2, '0')}` : `${h}`
}

export const pad = (n: number) => String(n).padStart(2, '0')
export const ymd = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
export const monthKey = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}`
export const monthRange = (key: string) => {
  const [y, m] = key.split('-').map(Number) as [number, number]
  return { start: `${y}-${pad(m)}-01`, end: ymd(new Date(y, m, 0)) }
}
export const shiftMonth = (key: string, delta: number) => {
  const [y, m] = key.split('-').map(Number) as [number, number]
  return monthKey(new Date(y, m - 1 + delta, 1))
}

export const currentYear = () => new Date().getFullYear()
export const currentMonth = () => monthKey(new Date())
