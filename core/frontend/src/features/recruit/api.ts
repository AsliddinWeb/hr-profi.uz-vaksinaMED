export const STAGES = ['new', 'screening', 'interview', 'offer', 'hired', 'rejected'] as const
export type Stage = (typeof STAGES)[number]
export const MOVABLE = ['new', 'screening', 'interview', 'offer'] as const
export const SOURCES = ['walk_in', 'referral', 'telegram', 'olx', 'hh', 'social', 'other'] as const
export type VStatus = 'draft' | 'open' | 'paused' | 'closed'

export interface Ref {
  id: number
  name: string | null
}

export interface Vacancy {
  id: number
  title: string
  status: VStatus
  openings: number
  hired: number
  filled: boolean
  branch: Ref | null
  department: Ref | null
  position: Ref | null
  description: string | null
  requirements: string | null
  salary_from: number | null
  salary_to: number | null
  deadline: string | null
  recruiter: Ref | null
  opened_at: string | null
  closed_at: string | null
  created_at: string
  funnel: Record<Stage, number> | null
}

export interface VacancyPage {
  total: number
  page: number
  size: number
  items: Vacancy[]
}

export interface Candidate {
  id: number
  full_name: string
  phone: string | null
  email: string | null
  birth_date: string | null
  address: string | null
  source: string | null
  skills: string[]
  note: string | null
  pinfl?: string | null
  profile_confirmed_at?: string | null
}

export interface CandidateRow extends Candidate {
  applications: number
  created_at: string
}

export interface CandidateDetail extends Candidate {
  resume_text: string | null
  created_at: string
  applications: { id: number; vacancy: { id: number; title: string | null }; stage: Stage; applied_at: string }[]
  files: { id: number; filename: string; mime: string; size: number; created_at: string }[]
}

export interface Application {
  id: number
  stage: Stage
  rating: number | null
  reject_reason: string | null
  interview_at: string | null
  applied_at: string
  stage_changed_at: string
  candidate: { id: number; full_name: string | null; phone: string | null; source: string | null; skills: string[] }
  vacancy: { id: number; title: string | null }
  recruiter: Ref | null
  employee_id: number | null
  hired_at: string | null
  experience_level: 'high' | 'mid' | 'none' | null
  stages_unlocked: ('intern' | 'pharmacist' | 'senior')[]
  hard_skill: number | null
  soft_skill: number | null
  interview_notes: string | null
  interviewed_at: string | null
  bg_status: 'pending' | 'passed' | 'failed' | null
  bg_note: string | null
  ai_scan: { score: number | null; summary: string; strengths: string[]; risks: string[]; questions: string[]; recommendation: 'advance' | 'hold' | 'reject'; model: string } | null
  ai_scan_at: string | null
  offer: { status: 'pending_hrd' | 'approved' | 'rejected'; level: string | null; salary: number | null; start: string | null; note: string | null; decision_note: string | null; sent_at: string | null } | null
  has_telegram: boolean
  reject_code: string | null
  match_score: number | null
  match_detail: { parts: { key: string; weight: number; ratio: number; hit?: string[]; miss?: string[]; have?: number | null; need?: number }[]; excluded: string[] } | null
}

export interface ApplicationDetail extends Application {
  vacancy: { id: number; title: string | null; status: VStatus; branch_id: number | null; department_id: number | null; position_id: number | null }
  can: { manage: boolean; hire: boolean; approve: boolean }
  events: { id: number; action: string; from: Stage | null; to: Stage | null; note: string | null; data: Record<string, unknown> | null; actor: string | null; created_at: string }[]
}

export interface Page<T> {
  total: number
  page: number
  size: number
  items: T[]
}

export type Board = Record<Stage, { total: number; items: Application[] }>

export interface Summary {
  start: string
  end: string
  applied: number
  hired: number
  rejected: number
  open_vacancies: number
  avg_days_to_hire: number | null
  stages: Record<Stage, number>
  sources: { source: string | null; applied: number; hired: number }[]
}

export const VSTATUS_TONE: Record<VStatus, 'neutral' | 'success' | 'warning' | 'danger'> = { draft: 'neutral', open: 'success', paused: 'warning', closed: 'danger' }
export const STAGE_TONE: Record<Stage, 'neutral' | 'success' | 'warning' | 'danger'> = { new: 'neutral', screening: 'neutral', interview: 'warning', offer: 'warning', hired: 'success', rejected: 'danger' }
export const money = (n: number | null): string => (n === null ? '' : new Intl.NumberFormat('ru-RU').format(n))
export const salaryText = (a: number | null, b: number | null): string => (a === null && b === null ? '—' : a !== null && b !== null ? `${money(a)} – ${money(b)}` : a !== null ? `${money(a)}+` : `≤ ${money(b)}`)

export const REJECT_CODES = ['no_answer', 'not_suitable', 'declined', 'salary', 'schedule', 'no_show', 'failed_test', 'failed_background', 'hired_elsewhere', 'other'] as const

export interface Invitation {
  id: number
  status: 'sent' | 'scheduled' | 'declined' | 'cancelled'
  mode: 'offline' | 'online'
  slots: string[]
  place: string | null
  map_url: string | null
  contact_phone: string | null
  meeting_url: string | null
  chosen_at: string | null
  reply: 'coming' | 'not_coming' | null
  url: string | null
  telegram_sent?: boolean
}

export interface CardProfile {
  duties: string | null
  hard_skills: string[]
  soft_skills: string[]
  languages: string[]
  education: string | null
  min_experience: number | null
  exclusions: string[]
}
