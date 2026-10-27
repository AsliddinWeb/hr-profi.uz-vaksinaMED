export interface Employee {
  id: number
  employee_no: number
  last_name: string
  first_name: string
  middle_name: string | null
  full_name: string
  gender: 'm' | 'f' | null
  phone: string | null
  phone2: string | null
  email: string | null
  has_photo: boolean
  department: { id: number; name: string } | null
  position: { id: number; name: string } | null
  branch: { id: number; number: number | null; name: string } | null
  work_group: { id: number; name: string } | null
  status: 'active' | 'dismissed'
  hire_date: string | null
  dismissal_date: string | null
  dismissal_reason: string | null
  dismissal_note: string | null
  user: { id: number; login: string; is_active: boolean } | null
  sensitive: boolean
  birth_date: string | null
  address: string | null
  passport_no: string | null
  pinfl: string | null
}

export interface EmployeePage {
  total: number
  page: number
  size: number
  summary: { total: number; active: number; dismissed: number; with_account: number }
  items: Employee[]
}

export interface DuplicateMatch {
  id: number
  employee_no: number
  full_name: string
  phone: string | null
  status: string
  reasons: string[]
}

export interface EmployeeEvent {
  id: number
  kind: 'hired' | 'transfer' | 'dismissed' | 'reinstated' | 'merged' | string
  effective_date: string
  data: Record<string, unknown> | null
  note: string | null
  actor: string | null
  created_at: string
}

export interface EmployeeDocument {
  id: number
  employee_id: number
  kind: string
  title: string
  filename: string
  mime: string
  size: number
  issued_at: string | null
  expires_at: string | null
  expired: boolean
  expires_soon: boolean
  note: string | null
  created_at: string
}

export const DOC_KINDS = ['passport', 'contract', 'diploma', 'medical', 'certificate', 'other'] as const
export const DISMISS_REASONS = ['own_will', 'contract_end', 'discipline', 'reduction', 'other'] as const

export interface BulkResultItem {
  id: number
  name: string | null
  ok: boolean
  error?: string
  login?: string
  temp_password?: string
}

export interface BulkResult {
  action: string
  total: number
  succeeded: number
  results: BulkResultItem[]
}

export const today = () => new Date().toISOString().slice(0, 10)

export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
