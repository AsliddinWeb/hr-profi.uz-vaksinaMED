import type { Shift } from '../schedule/api'

export type Status =
  | 'off' | 'holiday' | 'future' | 'pending' | 'absent' | 'working' | 'present' | 'late' | 'early'
  | 'late_early' | 'no_checkout' | 'incomplete' | 'unscheduled' | 'leave' | 'exempt' | 'no_shift'

export const STATUSES: Status[] = [
  'present', 'late', 'early', 'late_early', 'working', 'no_checkout', 'incomplete', 'absent', 'pending',
  'unscheduled', 'leave', 'off', 'holiday', 'exempt', 'no_shift', 'future',
]

/** Tabel belgilari (Excel eksport bilan bir xil). */
export const CODES: Record<Status, string> = {
  present: '+', late: 'K', early: 'E', late_early: 'KE', working: '…', no_checkout: '?', incomplete: '!',
  absent: 'Y', off: 'D', holiday: 'B', future: '', pending: '', exempt: '', no_shift: '', unscheduled: '+', leave: 'R',
}

export const TONES: Record<Status, string> = {
  present: 'bg-success/12 text-success',
  unscheduled: 'bg-success/12 text-success',
  leave: 'bg-info/12 text-info',
  late: 'bg-warning/16 text-warning',
  early: 'bg-warning/16 text-warning',
  late_early: 'bg-warning/24 text-warning',
  incomplete: 'bg-warning/16 text-warning',
  absent: 'bg-danger/10 text-danger',
  holiday: 'bg-danger/8 text-danger/80',
  working: 'bg-info/12 text-info',
  no_checkout: 'bg-warning/16 text-warning',
  off: 'bg-surface-3 text-muted',
  pending: 'bg-surface-2 text-muted',
  exempt: 'bg-surface-2 text-muted',
  no_shift: 'bg-surface-2 text-muted',
  future: 'bg-surface-2 text-muted',
}

export interface AttRecord {
  id: number
  employee_id: number
  work_date: string
  shift_id: number | null
  shift_name: string | null
  planned_start: string | null
  planned_end: string | null
  check_in_at: string
  check_out_at: string | null
  in_method: string
  out_method: string | null
  branch_id: number | null
  in_distance_m: number | null
  out_distance_m: number | null
  late_minutes: number
  early_leave_minutes: number
  worked_minutes: number
  is_manual: boolean
  note: string | null
}

export interface MeData {
  employee: { id: number; full_name: string }
  today: string
  now: string
  schedule: { working: boolean; reason: string; shift: Shift | null }
  open_record: AttRecord | null
  recent: AttRecord[]
  branch: { id: number; name: string; has_geo: boolean; radius: number } | null
}

export interface PunchResult {
  action: 'check_in' | 'check_out'
  record: AttRecord
}

export interface DailyItem {
  employee: { id: number; employee_no: number; full_name: string }
  status: Status
  shift: { id: number; name: string; start_time: string; end_time: string } | null
  record: AttRecord | null
}

export interface Daily {
  date: string
  total: number
  page: number
  size: number
  summary: Record<Status, number>
  items: DailyItem[]
}

export interface Totals {
  worked_days: number
  absent: number
  late_count: number
  late_minutes: number
  early_count: number
  early_minutes: number
  worked_minutes: number
  no_checkout: number
  scheduled_days: number
}

export interface Timesheet {
  total: number
  page: number
  size: number
  days: { date: string; weekday: number; holiday: string | null }[]
  rows: {
    employee: { id: number; employee_no: number; full_name: string; position: string | null }
    cells: { status: Status; record_id: number | null; late: number; worked: number }[]
    totals: Totals
  }[]
}

export interface DayInfo {
  employee: { id: number; full_name: string; status: string }
  date: string
  scheduled_shift: Shift | null
  reason: string
  record: AttRecord | null
}

export interface RecordDetail extends AttRecord {
  employee: { id: number; full_name: string } | null
  corrections: {
    id: number
    action: 'create' | 'update' | 'delete'
    reason: string
    before: Record<string, unknown> | null
    after: Record<string, unknown> | null
    actor_id: number | null
    created_at: string
  }[]
}

export interface QrData {
  branch: { id: number; number: number | null; name: string; has_geo: boolean }
  token: string
  url: string
  svg: string
  expires_in: number
}

const TZ = 'Asia/Tashkent'
const UTC_OFFSET = '+05:00' // O'zbekistonda yozgi vaqt yo'q

export function fmtTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit', timeZone: TZ }).format(new Date(iso))
}

export function fmtMin(min: number): string {
  const h = Math.floor(min / 60)
  const m = min % 60
  return `${h}:${String(m).padStart(2, '0')}`
}

/** ISO -> `YYYY-MM-DDTHH:mm` (datetime-local qiymati, Toshkent vaqti). */
export function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return ''
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).formatToParts(new Date(iso))
  const p = Object.fromEntries(parts.map((x) => [x.type, x.value]))
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`
}

/** `YYYY-MM-DDTHH:mm` (Toshkent) -> ISO. */
export const fromLocalInput = (v: string): string | null => (v ? `${v}:00${UTC_OFFSET}` : null)

export const todayLocal = (): string =>
  new Intl.DateTimeFormat('en-CA', { timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())

export const addDays = (ymd: string, n: number): string => {
  const d = new Date(`${ymd}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + n)
  return d.toISOString().slice(0, 10)
}

export const mondayOf = (ymd: string): string => {
  const wd = (new Date(`${ymd}T00:00:00Z`).getUTCDay() + 6) % 7
  return addDays(ymd, -wd)
}

export const METHODS = ['qr', 'gps', 'manual', 'face'] as const

export interface GroupRow {
  id: number | null
  name: string | null
  employees: number
  attended: number
  absent: number
  late_count: number
  late_minutes: number
  rate: number | null
}

export interface Dashboard {
  start: string
  end: string
  kpis: GroupRow extends infer G
    ? Omit<G, 'id' | 'name'> & { early_count: number; worked_minutes: number; punctuality: number | null; no_checkout: number; scheduled_days: number }
    : never
  statuses: Partial<Record<Status, number>>
  trend: { date: string; attended: number; late: number; absent: number; rate: number | null }[]
  by_department: GroupRow[]
  by_branch: GroupRow[]
  top_late: { employee: { id: number; full_name: string }; late_count: number; late_minutes: number }[]
  top_absent: { employee: { id: number; full_name: string }; absent: number }[]
  /** Oldingi teng davr ko'rsatkichlari (taqqoslash) */
  previous?: { start: string; end: string; kpis: Dashboard['kpis'] }
}

export const pct = (v: number | null | undefined): string => (v === null || v === undefined ? '—' : `${(v * 100).toFixed(1)}%`)
