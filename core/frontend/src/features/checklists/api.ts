export type Kind = 'yesno' | 'score'

export interface Item {
  id: string
  section: string | null
  text: string
  kind: Kind
  weight: number
  required: boolean
  critical: boolean
}

export interface Template {
  id: number
  name: string
  description: string | null
  is_active: boolean
  item_count: number
  used: number
  items?: Item[]
}

export interface Answer extends Item {
  value: number | null
  na: boolean
  comment: string | null
}

export interface Visit {
  id: number
  status: 'draft' | 'submitted'
  template: { id: number | null; name: string }
  branch: { id: number; name: string | null } | null
  coordinator: { id: number; name: string | null } | null
  started_at: string
  submitted_at: string | null
  score: number | null
  critical_fails: number
  geo_ok: boolean
  distance_m: number | null
  answered: number
  total: number
}

export interface VisitFile {
  id: number
  item_id: string | null
  filename: string
  mime: string
  size: number
  created_at: string
}

export interface VisitDetail extends Visit {
  answers: Answer[]
  note: string | null
  geo_reason: string | null
  can: { edit: boolean; delete: boolean }
  files: VisitFile[]
}

export interface VisitPage {
  total: number
  page: number
  size: number
  items: Visit[]
}

export interface CoverageRow {
  branch: { id: number; name: string; number: number | null }
  coordinator: { id: number; name: string | null } | null
  visits: number
  avg_score: number | null
  last_at: string | null
  last_score: number | null
  days_since: number | null
  overdue: boolean
}

export interface Ranking {
  branches: { id: number; name: string | null; visits: number; avg_score: number | null; critical_fails: number }[]
  coordinators: { id: number; name: string | null; visits: number; avg_score: number | null; branches: number }[]
}

export type TrendPoint = { week: string; visits: number; avg_score: number | null }

export const scoreTone = (s: number | null): 'success' | 'warning' | 'danger' | 'neutral' => (s === null ? 'neutral' : s >= 85 ? 'success' : s >= 60 ? 'warning' : 'danger')
export const scoreText = (s: number | null): string => (s === null ? '—' : `${Number.isInteger(s) ? s : s.toFixed(1)}%`)
