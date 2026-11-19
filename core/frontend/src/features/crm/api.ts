import { CalendarCheck, Mail, Phone, Users, type LucideIcon } from 'lucide-react'

export const KINDS = ['call', 'meeting', 'email', 'task'] as const
export type Kind = (typeof KINDS)[number]
export const KIND_ICON: Record<Kind, LucideIcon> = { call: Phone, meeting: Users, email: Mail, task: CalendarCheck }

export interface Person {
  id: number
  name: string | null
}

export interface Stage {
  id: number
  name: string
  probability: number
  sort_order: number
  is_won: boolean
  auto_activity: string | null
  auto_activity_kind: Kind
  auto_activity_days: number
  is_active: boolean
}

export interface ActState {
  state: 'overdue' | 'today' | 'planned'
  days: number
  due: string
}

export interface DealCard {
  id: number
  title: string
  company: string | null
  contact_name: string | null
  amount: number
  probability: number
  priority: number
  tags: string[]
  stage_id: number
  owner: Person | null
  expected_close: string | null
  created_at: string
  won: boolean
  lost: boolean
  next_activity: ({ id: number; kind: Kind; title: string } & ActState) | null
  stage?: string | null
  lost_reason?: string | null
}

export interface Column extends Stage {
  count: number
  total: number
  overdue: number
  deals: DealCard[]
}

export interface Board {
  stages: Column[]
  can_create: boolean
  can_manage: boolean
  sees_all: boolean
}

export interface Deal extends DealCard {
  phone: string | null
  email: string | null
  source: string | null
  description: string | null
  lost_reason: string | null
  won_at: string | null
  lost_at: string | null
  created_by: string | null
  stage_changed_at: string | null
  updated_at: string
  stages: Stage[]
  can_edit: boolean
  can_assign: boolean
}

export interface Planned extends ActState {
  id: number
  kind: Kind
  title: string
  note: string | null
  due_date: string
  auto: boolean
  assignee: Person | null
  created_by: string | null
  can_done: boolean
}

export interface FeedItem {
  id: number
  kind: 'message' | 'note' | 'event'
  body: string | null
  data: Record<string, unknown> | null
  author: string | null
  author_id: number | null
  created_at: string
}

export interface Feed {
  planned: Planned[]
  items: FeedItem[]
  can_write: boolean
}

export interface MyActivity extends ActState {
  id: number
  kind: Kind
  title: string
  note: string | null
  due_date: string
  auto: boolean
  assignee: string | null
  deal: { id: number; title: string; company: string | null; phone: string | null; amount: number }
}

export interface Stats {
  days: number
  funnel: { id: number; name: string; is_won: boolean; count: number; total: number }[]
  new: number
  won: number
  won_amount: number
  lost: number
  win_rate: number | null
  weighted_pipeline: number
  overdue_activities: number
  lost_reasons: { reason: string; count: number }[]
  top_owners: { name: string; won: number; amount: number }[]
}

export interface DealInput {
  title: string
  company: string | null
  contact_name: string | null
  phone: string | null
  email: string | null
  amount: number
  probability: number | null
  priority: number
  tags: string[]
  source: string | null
  description: string | null
  expected_close: string | null
  stage_id: number | null
  owner_id: number | null
}

/** Qisqa summa: 1.1 mlrd, 860 mln, 25 ming (UZS). */
export function shortMoney(n: number, lang: string): string {
  const ru = lang === 'ru'
  const f = (v: number) => (Math.round(v * 10) / 10).toLocaleString(ru ? 'ru-RU' : 'en-US', { maximumFractionDigits: 1 })
  if (n >= 1e9) return `${f(n / 1e9)} ${ru ? 'млрд' : 'mlrd'}`
  if (n >= 1e6) return `${f(n / 1e6)} ${ru ? 'млн' : 'mln'}`
  if (n >= 1e3) return `${f(n / 1e3)} ${ru ? 'тыс' : 'ming'}`
  return String(Math.round(n))
}

export const STATE_TONE: Record<ActState['state'], string> = {
  overdue: 'bg-danger/12 text-danger',
  today: 'bg-warning/15 text-warning',
  planned: 'bg-success/12 text-success',
}

export const todayIso = (shift = 0) => {
  const d = new Date()
  d.setDate(d.getDate() + shift)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
