export const PURPOSES = ['meeting', 'interview', 'delivery', 'service', 'other'] as const
export type Purpose = (typeof PURPOSES)[number]
export const STATUSES = ['expected', 'arrived', 'left', 'cancelled', 'no_show'] as const
export type VStatus = (typeof STATUSES)[number]

export const STATUS_TONE: Record<VStatus, 'neutral' | 'warning' | 'success' | 'danger'> = {
  expected: 'warning',
  arrived: 'success',
  left: 'neutral',
  cancelled: 'neutral',
  no_show: 'danger',
}

export interface Visit {
  id: number
  visitor_name: string
  visitor_phone: string | null
  company: string | null
  purpose: Purpose
  status: VStatus
  host: { id: number; name: string | null } | null
  branch: { id: number; name: string | null } | null
  expected_at: string | null
  arrived_at: string | null
  left_at: string | null
  inside: boolean
  badge_no: string | null
  doc_info: string | null
  vehicle_plate: string | null
  note: string | null
  registered_by: string | null
  checked_in_by: string | null
  checked_out_by: string | null
  created_at: string
}

export interface VisitDetail extends Visit {
  can: { edit: boolean; arrive: boolean; leave: boolean; cancel: boolean }
}

export interface VisitPage {
  total: number
  page: number
  size: number
  items: Visit[]
}

export interface Report {
  start: string
  end: string
  total: number
  inside_now: number
  no_show: number
  avg_minutes: number | null
  by_purpose: Record<Purpose, number>
  trend: { date: string; count: number }[]
  top_hosts: { name: string | null; count: number }[]
}
