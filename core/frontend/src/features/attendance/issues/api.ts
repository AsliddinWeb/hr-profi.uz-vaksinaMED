export type IssueStatus = 'pending_coordinator' | 'pending_hr' | 'approved' | 'rejected' | 'cancelled'
export const ISSUE_STATUSES: IssueStatus[] = ['pending_coordinator', 'pending_hr', 'approved', 'rejected', 'cancelled']
export const ISSUE_KINDS = ['missed_in', 'missed_out', 'wrong_checkout', 'other'] as const
export const ISSUE_METHODS = ['qr', 'face', 'gps', 'other'] as const

export const ISSUE_TONE: Record<IssueStatus, 'neutral' | 'success' | 'warning' | 'danger'> = {
  pending_coordinator: 'warning',
  pending_hr: 'warning',
  approved: 'success',
  rejected: 'danger',
  cancelled: 'neutral',
}

export interface AttendanceIssue {
  id: number
  employee: { id: number; employee_no: number; full_name: string }
  branch: string | null
  work_date: string
  kind: (typeof ISSUE_KINDS)[number]
  method_tried: (typeof ISSUE_METHODS)[number]
  claimed_in: string | null
  claimed_out: string | null
  comment: string
  status: IssueStatus
  decided_at: string | null
  decision_note: string | null
  created_at: string
  history: { action: 'submitted' | 'verified' | 'approved' | 'rejected' | 'cancelled'; actor: string | null; level: string | null; note: string | null; at: string }[]
  can_verify: boolean
  can_decide: boolean
  can_cancel: boolean
}

export interface IssuePage {
  total: number
  page: number
  size: number
  items: AttendanceIssue[]
}
