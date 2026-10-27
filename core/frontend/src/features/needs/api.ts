export const STAGES = ['requested', 'assigned', 'completed', 'confirmed'] as const
export type NStatus = (typeof STAGES)[number] | 'cancelled'
export const PRIORITIES = ['low', 'normal', 'high', 'urgent'] as const
export type Priority = (typeof PRIORITIES)[number]

export const PRIORITY_TONE: Record<Priority, string> = {
  low: 'bg-surface-2 text-muted',
  normal: 'bg-info/15 text-info',
  high: 'bg-warning/20 text-warning',
  urgent: 'bg-danger/15 text-danger',
}

export interface Person {
  id: number
  name: string | null
}

export interface Need {
  id: number
  number: string
  title: string
  status: NStatus
  priority: Priority
  due_at: string | null
  overdue: boolean
  category: { id: number; name: string | null } | null
  branch: { id: number; name: string | null } | null
  requester: Person | null
  assignee: Person | null
  requested_at: string
  assigned_at: string | null
  completed_at: string | null
  confirmed_at: string | null
  return_count: number
  rating: number | null
  comments: number
  files: number
}

export interface NeedDetail extends Need {
  description: string | null
  report: string | null
  confirm_note: string | null
  can: { edit: boolean; assign: boolean; complete: boolean; confirm: boolean; cancel: boolean; collaborate: boolean }
  events: { id: number; action: string; note: string | null; data: Record<string, unknown> | null; actor: string | null; created_at: string }[]
}

export interface NeedPage {
  total: number
  page: number
  size: number
  items: Need[]
}

export interface Category {
  id: number
  name: string
  description: string | null
  sla_days: number | null
  sort_order: number
  is_active: boolean
  default_assignee: Person | null
  used: number
}

export interface NeedComment {
  id: number
  author: Person
  body: string
  created_at: string
}

export interface NeedFile {
  id: number
  filename: string
  mime: string
  size: number
  uploaded_by: string | null
  created_at: string
}

interface Row {
  name: string | null
  created: number
  done: number
  open: number
  overdue: number
  avg_hours: number | null
  rating: number | null
}

export interface Analytics {
  start: string
  end: string
  kpis: { created: number; completed: number; confirmed: number; open: number; overdue: number; unassigned: number; on_time_rate: number | null; return_rate: number | null; avg_hours: number | null; avg_rating: number | null }
  by_status: Record<NStatus, number>
  trend: { date: string; created: number; completed: number }[]
  by_category: Row[]
  by_executor: Row[]
  by_branch: Row[]
}

export const STATUS_TONE: Record<NStatus, 'neutral' | 'warning' | 'success' | 'danger'> = {
  requested: 'warning',
  assigned: 'neutral',
  completed: 'warning',
  confirmed: 'success',
  cancelled: 'neutral',
}

export const sizeText = (b: number): string => (b < 1024 * 1024 ? `${Math.max(1, Math.round(b / 1024))} KB` : `${(b / 1024 / 1024).toFixed(1)} MB`)
