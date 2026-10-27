export type Kind = 'day' | 'hourly'
export type Status = 'pending_coordinator' | 'pending_hr' | 'approved' | 'rejected' | 'cancelled'
export const REASONS = ['sick', 'family', 'personal', 'business', 'other'] as const
export const STATUSES: Status[] = ['pending_coordinator', 'pending_hr', 'approved', 'rejected', 'cancelled']

export const STATUS_TONE: Record<Status, 'neutral' | 'success' | 'warning' | 'danger'> = {
  pending_coordinator: 'warning',
  pending_hr: 'warning',
  approved: 'success',
  rejected: 'danger',
  cancelled: 'neutral',
}

export interface LeaveRequest {
  id: number
  employee: { id: number; employee_no: number; full_name: string }
  kind: Kind
  reason_type: (typeof REASONS)[number]
  reason: string | null
  start_date: string
  end_date: string
  start_time: string | null
  end_time: string | null
  status: Status
  submitted_at: string
  escalate_at: string | null
  escalated_at: string | null
  decided_at: string | null
  decided_level: 'coordinator' | 'hr' | null
  decision_note: string | null
  can_decide: boolean
  can_cancel: boolean
}

export interface LeaveDetail extends LeaveRequest {
  coordinator: string | null
  events: { id: number; action: 'submitted' | 'escalated' | 'approved' | 'rejected' | 'cancelled'; level: string | null; note: string | null; actor: string | null; created_at: string }[]
}

export interface LeavePage {
  total: number
  page: number
  size: number
  items: LeaveRequest[]
}

export interface CalendarItem {
  id: number
  employee: { id: number; full_name: string }
  kind: Kind
  reason_type: string
  status: Status
  start_date: string
  end_date: string
  start_time: string | null
  end_time: string | null
}

const fmt = (d: string) => d.split('-').reverse().join('.')

/** "04.11.2026 – 05.11.2026" yoki "03.11.2026 15:00–17:00". */
export function period(r: Pick<LeaveRequest, 'kind' | 'start_date' | 'end_date' | 'start_time' | 'end_time'>): string {
  if (r.kind === 'hourly') return `${fmt(r.start_date)} ${r.start_time}–${r.end_time}`
  return r.start_date === r.end_date ? fmt(r.start_date) : `${fmt(r.start_date)} – ${fmt(r.end_date)}`
}

/** Eskalatsiyagacha qolgan vaqt (daqiqa); o'tib ketgan bo'lsa 0. */
export function minutesLeft(iso: string | null, now: number): number | null {
  if (!iso) return null
  return Math.max(0, Math.round((new Date(iso).getTime() - now) / 60000))
}

export function fmtLeft(min: number): string {
  const h = Math.floor(min / 60)
  const m = min % 60
  return h ? `${h} soat ${m} daq` : `${m} daq`
}
