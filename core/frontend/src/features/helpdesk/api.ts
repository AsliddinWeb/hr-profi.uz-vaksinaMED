export const STATUSES = ['new', 'in_progress', 'waiting', 'resolved', 'closed', 'cancelled'] as const
export type TStatus = (typeof STATUSES)[number]
export const FLOW = ['new', 'in_progress', 'resolved', 'closed'] as const
export const PRIORITIES = ['low', 'normal', 'high', 'urgent'] as const
export type Priority = (typeof PRIORITIES)[number]

export const PRIORITY_TONE: Record<Priority, string> = {
  low: 'bg-surface-2 text-muted',
  normal: 'bg-info/15 text-info',
  high: 'bg-warning/20 text-warning',
  urgent: 'bg-danger/15 text-danger',
}

export const STATUS_TONE: Record<TStatus, 'neutral' | 'warning' | 'success' | 'danger'> = {
  new: 'warning',
  in_progress: 'neutral',
  waiting: 'warning',
  resolved: 'success',
  closed: 'success',
  cancelled: 'neutral',
}

export interface Person {
  id: number
  name: string | null
}

export interface Ticket {
  id: number
  number: string
  title: string
  status: TStatus
  priority: Priority
  due_at: string | null
  overdue: boolean
  sla_breached: boolean
  category: { id: number; name: string | null } | null
  branch: { id: number; name: string | null } | null
  requester: Person | null
  assignee: Person | null
  opened_at: string
  first_response_at: string | null
  resolved_at: string | null
  closed_at: string | null
  rating: number | null
  reopen_count: number
  device_info: string | null
  comments: number
  files: number
}

export interface TicketEvent {
  id: number
  action: string
  from_status: TStatus | null
  to_status: TStatus | null
  note: string | null
  data: Record<string, unknown> | null
  actor: string | null
  actor_id: number | null
  created_at: string
}

export interface TicketDetail extends Ticket {
  description: string | null
  resolution: string | null
  rating_comment: string | null
  can: { edit: boolean; take: boolean; assign: boolean; work: boolean; close: boolean; reopen: boolean; cancel: boolean; internal: boolean; collaborate: boolean }
  events: TicketEvent[]
}

export interface TicketPage {
  total: number
  page: number
  size: number
  items: Ticket[]
}

export interface Category {
  id: number
  name: string
  description: string | null
  sort_order: number
  is_active: boolean
  default_assignee: Person | null
  used: number
}

export interface TicketFile {
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
  kpis: { created: number; resolved: number; open: number; overdue: number; unassigned: number; sla_rate: number | null; reopen_rate: number | null; avg_resolution_hours: number | null; avg_response_minutes: number | null; avg_rating: number | null }
  by_status: Record<TStatus, number>
  by_priority: Record<Priority, number>
  by_category: Row[]
  by_executor: Row[]
}

export const SLA_HOURS: Record<Priority, number> = { urgent: 4, high: 8, normal: 24, low: 72 }
