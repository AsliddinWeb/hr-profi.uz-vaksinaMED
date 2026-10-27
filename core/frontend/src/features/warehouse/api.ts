export interface WhRow {
  id: number
  name: string
  branch: { id: number; name: string } | null
  work_group: { id: number; name: string } | null
  shift: { id: number; name: string; kind: string; start: string; end: string; min_work_minutes: number | null } | null
  min_on_duty: number
  max_shift_hours: number
  alert_grace_min: number
  is_active: boolean
  status?: { on_duty: number; expected: number; gap: boolean; in_window: boolean; staff: number; long_open: number }
}

export interface StaffState {
  employee: { id: number; name: string; employee_no: number }
  status: string
  scheduled: boolean
  check_in_at: string | null
  check_out_at: string | null
  worked_minutes: number
  on_duty: boolean
  met_min: boolean | null
  remaining_minutes: number | null
}

export interface WhStatus {
  warehouse: { id: number; name: string; min_on_duty: number; max_shift_hours: number; is_active: boolean }
  staff: StaffState[]
  on_duty: number
  expected: number
  gap: boolean
  in_window: boolean
  no_shift: boolean
  long_open: { employee_id: number; name: string; record_id: number; hours: number }[]
  window: { date: string; start: string; end: string; min_work_minutes: number; kind: string; shift: string } | null
}

export interface Control {
  start: string
  end: string
  no_shift: boolean
  employees: { employee: { id: number; name: string; employee_no: number }; days: number; scheduled: number; worked_minutes: number; avg_minutes: number; longest_minutes: number; below_min: number; absent: number; no_checkout: number; leave: number }[]
  days: { date: string; staff_in: number; peak: number; lowest: number; gap_minutes: number; window_minutes: number; open: number }[]
  totals: { worked_hours: number; below_min: number; absent: number; gap_minutes: number; gap_days: number; min_work_minutes: number }
}

export const hm = (m: number): string => `${Math.floor(m / 60)}:${String(m % 60).padStart(2, '0')}`
