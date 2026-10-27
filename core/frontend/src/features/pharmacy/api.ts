export const ROLES = ['manager', 'pharmacist', 'intern'] as const
export type Role = (typeof ROLES)[number] | 'other'
export type Severity = 'uncovered' | 'short' | 'ok'

export const SEV_COLOR: Record<Severity, string> = { uncovered: '#e11d48', short: '#f59e0b', ok: '#12a150' }
export const SEV_TONE: Record<Severity, 'danger' | 'warning' | 'success'> = { uncovered: 'danger', short: 'warning', ok: 'success' }

export interface Today {
  expected: number
  here_now: number
  attended: number
  late: number
  absent: number
  leave: number
  pending: number
}

export interface BranchRow {
  id: number
  number: number | null
  name: string
  district: string | null
  address: string | null
  phone: string | null
  manager: { id: number; name: string | null } | null
  coordinator: { id: number; name: string | null } | null
  has_geo: boolean
  is_active: boolean
  norm: Record<(typeof ROLES)[number], number>
  counts: Record<Role, number>
  gaps: Partial<Record<(typeof ROLES)[number], number>>
  headcount: number
  today: Today
  flags: string[]
  severity: Severity
  open_needs: number
  open_needs_list: { id: number; role: Role; count: number; urgency: string }[]
  hours: { is_24h: boolean; open: string | null; close: string | null }
}

export interface Overview {
  kpis: { branches: number; uncovered: number; short: number; ok: number; with_needs: number; open_needs: number; expected: number; attended: number; absent: number; late: number; headcount: number }
  total: number
  page: number
  size: number
  districts: string[]
  items: BranchRow[]
}

export interface MapPoint {
  id: number
  number: number | null
  name: string
  lat: number
  lng: number
  severity: Severity
  flags: string[]
  headcount: number
  gaps: Record<string, number>
  here_now: number
  open_needs: number
}

export interface Need {
  id: number
  branch: { id: number; number: number | null; name: string } | null
  role: Role
  count: number
  urgency: 'low' | 'normal' | 'urgent'
  needed_from: string | null
  reason: string | null
  status: 'open' | 'filled' | 'cancelled'
  created_at: string
  created_by: string | null
  closed_at: string | null
  close_note: string | null
  closed_by?: string | null
  can_edit?: boolean
  can_close?: boolean
  approval: 'pending_hr' | 'pending_hrd' | 'approved' | 'rejected'
  reason_type: string | null
  shift_note: string | null
  position_id: number | null
  vacancy_id: number | null
  decision_note: string | null
  can_forward?: boolean
  can_approve?: boolean
  can_reject?: boolean
}

export interface BranchCard extends BranchRow {
  team: {
    employee: { id: number; employee_no: number; full_name: string; phone: string | null; has_photo: boolean }
    position: string | null
    role: Role
    status: string
    expected: boolean
    check_in_at: string | null
    check_out_at: string | null
    late_minutes: number
    shift: string | null
  }[]
  week: { date: string; scheduled: number; by_role: Record<Role, number>; uncovered: boolean }[]
  note: string | null
  latitude: number | null
  longitude: number | null
  geofence_radius_m: number
  needs: Need[]
  closed_needs: Need[]
  can_manage: boolean
  can_request: boolean
}

export interface Quality {
  branches: number
  active: number
  complete: number
  issues: { code: string; count: number; branches: { id: number; number: number | null; name: string }[] }[]
}

export const branchTitle = (b: { number: number | null; name: string }) => (b.number ? `№${b.number} · ${b.name}` : b.name)
