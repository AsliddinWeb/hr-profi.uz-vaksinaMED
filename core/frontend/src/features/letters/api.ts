export const INCIDENTS = ['late', 'absent', 'early_leave', 'no_checkout', 'discipline', 'other'] as const
export type Incident = (typeof INCIDENTS)[number]
export type LetterStatus = 'requested' | 'submitted' | 'accepted' | 'returned' | 'cancelled'
export const LETTER_STATUSES: LetterStatus[] = ['requested', 'submitted', 'accepted', 'returned', 'cancelled']

export const STATUS_TONE: Record<LetterStatus, 'neutral' | 'success' | 'warning' | 'danger'> = {
  requested: 'warning',
  submitted: 'neutral',
  accepted: 'success',
  returned: 'danger',
  cancelled: 'neutral',
}

export interface Letter {
  id: number
  number: string
  code: string
  employee: { id: number; employee_no: number; full_name: string }
  incident_type: Incident
  incident_date: string
  incident_note: string | null
  due_date: string | null
  overdue: boolean
  status: LetterStatus
  requested_at: string
  requested_by: string | null
  submitted_at: string | null
  reviewed_at: string | null
  review_note: string | null
  has_scan: boolean
  scan_filename: string | null
  template_id: number | null
  signed: boolean
  content_hash: string | null
  can_write: boolean
  can_review: boolean
  can_cancel: boolean
  can_scan: boolean
}

export interface LetterDetail extends Letter {
  instructions: string | null
  explanation: string | null
  snapshot: { title: string; recipient: string; body: string; employee_name: string; company: string; date: string; incident: string } | null
  signature: { name: string; at: string } | null
  events: { id: number; action: string; note: string | null; actor: string | null; created_at: string }[]
}

export interface LetterPage {
  total: number
  page: number
  size: number
  items: Letter[]
}

export interface LetterTemplate {
  id: number
  name: string
  title: string
  recipient_line: string
  body_template: string
  instructions: string | null
  is_default: boolean
  is_active: boolean
  used: number
}

export interface VerifyResult {
  valid: boolean
  intact: boolean
  number: string
  employee: string
  status: LetterStatus
  incident_type: Incident
  incident_date: string
  signed_at: string | null
  hash_prefix: string
  hash_match: boolean | null
}

/** Davomat holati -> xat sababi (kunlik davomat sahifasidagi "tushuntirish so'rash" havolasi uchun). */
export const STATUS_TO_INCIDENT: Record<string, Incident> = {
  late: 'late',
  late_early: 'late',
  absent: 'absent',
  early: 'early_leave',
  no_checkout: 'no_checkout',
}
