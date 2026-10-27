export type PStatus = 'pending' | 'approved' | 'cancelled'
export const PSTATUSES: PStatus[] = ['pending', 'approved', 'cancelled']
export const TYPES = ['late', 'absent', 'early_leave', 'no_checkout', 'discipline', 'other'] as const
export const AUTO_TYPES = ['late', 'early_leave', 'absent', 'no_checkout'] as const

export const TONE: Record<PStatus, 'warning' | 'danger' | 'neutral'> = { pending: 'warning', approved: 'danger', cancelled: 'neutral' }

export interface Penalty {
  id: number
  employee: { id: number; employee_no: number; full_name: string }
  incident_type: (typeof TYPES)[number]
  incident_date: string
  source: 'auto' | 'manual'
  step: number
  label: string
  amount: number
  block_days: number
  details: Record<string, unknown> | null
  reason: string | null
  status: PStatus
  rule_version_id: number | null
  created_at: string
  decided_at: string | null
  decision_note: string | null
  block_applied: boolean
  blocked_until: string | null
  unblocked_at: string | null
}

export interface PenaltyDetail extends Penalty {
  rule_version: number | null
  can_approve: boolean
  can_cancel: boolean
  letters: { id: number; number: string; status: string }[]
}

export interface PenaltyPage {
  total: number
  page: number
  size: number
  approved_amount: number
  items: Penalty[]
}

export interface RuleStep {
  step: number
  label: string
  amount: number
  block_days: number
}
export interface RulesConfig {
  auto_scan: boolean
  window_days: number
  count_mode: 'all' | 'per_type'
  triggers: Record<(typeof AUTO_TYPES)[number], { enabled: boolean; min_minutes: number }>
  steps: RuleStep[]
}
export interface RuleVersion {
  id: number
  version: number
  config: RulesConfig
  note: string | null
  created_at: string
  author: string | null
  used?: number
}
export interface RulesOverview {
  current: RuleVersion | null
  versions: RuleVersion[]
}

export interface ScanResult {
  employees: number
  created: number
  existing: number
  warnings: number
  fines: number
  blocks: number
  rule_version: number
  dry_run: boolean
}

export interface ReportRow {
  key: number | string | null
  name: string | null
  pending: number
  approved: number
  cancelled: number
  amount: number
  pending_amount: number
  blocks: number
}
export interface Report {
  start: string
  end: string
  group_by: string
  items: ReportRow[]
  totals: Omit<ReportRow, 'key' | 'name'>
}

export const money = (v: number): string => `${new Intl.NumberFormat('ru-RU').format(Math.round(v))} so'm`
