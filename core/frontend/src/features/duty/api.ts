export interface DutyItem {
  id?: string
  text: string
  kind: 'yesno' | 'score'
  required: boolean
}

export interface DutyTemplate {
  id: number
  name: string
  description: string | null
  scope: 'department' | 'position'
  frequency: 'daily' | 'weekly'
  deadline_time: string
  department_id: number | null
  position_id: number | null
  department: string | null
  position: string | null
  is_active: boolean
  item_count: number
  items?: (DutyItem & { id: string })[]
}

export type DutyStatus = 'done' | 'open' | 'overdue'

export interface MyDuty {
  employee: { id: number; name: string } | null
  items: {
    checklist: DutyTemplate & { items: (DutyItem & { id: string })[] }
    period_start: string
    due_at: string
    status: DutyStatus
    run: { answers: Record<string, boolean | number>; note: string | null; score_pct: number; completed_at: string; late: boolean } | null
  }[]
}

export interface DutyControl {
  date: string
  kpis: { expected: number; done: number; overdue: number; open: number; rate: number | null }
  by_department: { name: string; expected: number; done: number; rate: number }[]
  total: number
  rows: {
    employee: { id: number; name: string }
    branch: string | null
    department: string | null
    checklist: { id: number; name: string; frequency: 'daily' | 'weekly' }
    status: DutyStatus
    due_at: string
    completed_at: string | null
    score_pct: number | null
    late: boolean
  }[]
}

export const STATUS_TONE = { done: 'success', open: 'warning', overdue: 'danger' } as const
