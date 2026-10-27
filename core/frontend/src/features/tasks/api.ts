export const STATUSES = ['todo', 'in_progress', 'review', 'done'] as const
export type TStatus = (typeof STATUSES)[number]
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

export interface TaskItem {
  id: number
  title: string
  status: TStatus
  priority: Priority
  due_at: string | null
  overdue: boolean
  labels: string[]
  position: number
  completed_at: string | null
  created_at: string
  creator: Person | null
  assignee: Person | null
  comments: number
  files: number
  archived: boolean
}

export interface TaskDetail extends TaskItem {
  description: string | null
  watchers: Person[]
  can_edit: boolean
  can_collaborate: boolean
  allowed_status: TStatus[]
  events: { id: number; action: string; data: Record<string, unknown> | null; actor: string | null; created_at: string }[]
}

export interface TaskPage {
  total: number
  page: number
  size: number
  items: TaskItem[]
}

export type Board = Record<TStatus, { total: number; tasks: TaskItem[] }>

export interface Comment {
  id: number
  author: Person
  body: string
  created_at: string
}

export interface TaskFile {
  id: number
  filename: string
  mime: string
  size: number
  uploaded_by: string | null
  created_at: string
}

export interface TaskTemplate {
  id: number
  name: string
  title: string
  description: string | null
  priority: Priority
  due_days: number | null
  labels: string[]
  is_active: boolean
}

export interface Analytics {
  start: string
  end: string
  kpis: { created: number; completed: number; open: number; overdue: number; on_time_rate: number | null; avg_hours: number | null }
  by_status: Record<TStatus, number>
  by_priority: Record<Priority, number>
  trend: { date: string; created: number; completed: number }[]
  by_assignee: { user: { id: number; name: string | null }; assigned: number; done: number; open: number; overdue: number; avg_hours: number | null }[]
}

export type Scope = 'mine' | 'created' | 'watching' | 'all'

export function dueText(iso: string | null): string {
  if (!iso) return ''
  return new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Tashkent' }).format(new Date(iso))
}

export const sizeText = (b: number): string => (b < 1024 * 1024 ? `${Math.max(1, Math.round(b / 1024))} KB` : `${(b / 1024 / 1024).toFixed(1)} MB`)
