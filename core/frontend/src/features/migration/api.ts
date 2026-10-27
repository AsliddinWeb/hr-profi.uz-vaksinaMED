export type Dataset = 'employees' | 'attendance'
export const DATASETS: Dataset[] = ['employees', 'attendance']
export const METRICS = ['employees_total', 'employees_active', 'employees_dismissed', 'attendance_records', 'attendance_hours'] as const
export const MATCH_BY = ['legacy_id', 'employee_no', 'pinfl', 'phone'] as const

export const FIELDS: Record<Dataset, { key: string; required: boolean }[]> = {
  employees: ['legacy_id', 'full_name', 'last_name', 'first_name', 'middle_name', 'birth_date', 'gender', 'phone', 'email', 'address', 'pinfl', 'passport_no', 'department', 'position', 'branch', 'hire_date', 'dismissal_date', 'dismissal_reason'].map((key) => ({ key, required: false })),
  attendance: [
    { key: 'employee_ref', required: true },
    { key: 'work_date', required: true },
    { key: 'check_in', required: true },
    { key: 'check_out', required: false },
    { key: 'late_minutes', required: false },
  ],
}

export interface Summary {
  rows?: number
  created?: number
  linked?: number
  skipped?: number
  errors?: number
  new_refs?: { departments: number; positions: number; branches: number }
  stats?: { expected_minutes?: number; db_minutes?: number; reconciled?: boolean; employees?: number; date_from?: string | null; date_to?: string | null; dismissed?: number }
  rolled_back?: { attendance: number; employees: number }
}

export interface Batch {
  id: number
  dataset: Dataset
  filename: string
  status: 'draft' | 'previewed' | 'applied' | 'rolled_back'
  headers: string[]
  mapping: Record<string, string>
  options: { create_missing?: boolean; match_by?: string }
  summary: Summary
  issue_count: number
  created_by: string | null
  created_at: string
  applied_at: string | null
  rolled_back_at: string | null
  sample?: string[][]
  suggested?: Record<string, string>
}

export interface Issue {
  row: number
  status: 'error' | 'skipped'
  code: string
  field: string | null
  name: string | null
}

export interface Template {
  id: number
  name: string
  dataset: Dataset
  mapping: Record<string, string>
  options: { create_missing?: boolean; match_by?: string }
  updated_at: string
}

export interface Check {
  id: number
  label: string
  metric: (typeof METRICS)[number]
  period: string | null
  branch_id: number | null
  expected: number
  tolerance: number
  note: string | null
}

export interface ReconcileItem {
  id: number
  label: string
  metric: string
  period: string | null
  branch: { id: number; name: string | null } | null
  expected: number
  actual: number
  diff: number
  tolerance: number
  status: 'match' | 'mismatch'
}

export interface Reconcile {
  total: number
  matched: number
  mismatched: number
  items: ReconcileItem[]
}

export const BATCH_TONE: Record<Batch['status'], 'neutral' | 'warning' | 'success' | 'danger'> = { draft: 'neutral', previewed: 'warning', applied: 'success', rolled_back: 'danger' }
