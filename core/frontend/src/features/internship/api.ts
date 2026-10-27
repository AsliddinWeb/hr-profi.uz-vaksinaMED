export const KINDS = ['video', 'document', 'text', 'test'] as const
export type Kind = (typeof KINDS)[number]
export type EStatus = 'active' | 'ready' | 'completed' | 'cancelled'
export type SState = 'done' | 'available' | 'locked'

export interface Program {
  id: number
  name: string
  description: string | null
  pass_score: number
  sequential: boolean
  is_active: boolean
  steps: number
  enrolled: number
  phase: 'preboarding' | 'onboarding'
  position_id: number | null
  duration_days: number | null
}

export interface Question {
  id: string
  text: string
  options: string[]
  correct?: number[]
  multiple?: boolean
}

export interface Step {
  id: number
  program_id: number
  position: number
  kind: Kind
  title: string
  description: string | null
  url: string | null
  required: boolean
  pass_score: number | null
  max_attempts: number
  file: { name: string; mime: string; size: number } | null
  questions: Question[]
  question_count: number
}

export interface ProgramDetail extends Program {
  steps_list: Step[]
}

export interface Progress {
  required: number
  done: number
  percent: number
  avg_score: number | null
}

export interface Enrollment {
  id: number
  status: EStatus
  phase: 'preboarding' | 'onboarding'
  day7_decision: 'fit' | 'not_fit' | null
  started_at: string
  due_date: string | null
  ready_at: string | null
  completed_at: string | null
  final_score: number | null
  program: { id: number; name: string }
  employee: { id: number; name: string | null }
  mentor: { id: number; name: string | null } | null
  progress: Progress
  overdue: boolean
}

export interface StepState extends Step {
  state: SState
  score: number | null
  attempts: number
  completed_at: string | null
}

export interface EnrollmentDetail extends Enrollment {
  note: string | null
  pass_score: number
  sequential: boolean
  can: { confirm: boolean; cancel: boolean; reset: boolean; learn: boolean }
  steps: StepState[]
}

export interface Page<T> {
  total: number
  page: number
  size: number
  items: T[]
}

export interface TestResult {
  score: number
  passed: boolean
  wrong: string[]
  threshold: number
  attempts: number
  attempts_left: number | null
  status: EStatus
}

export const ESTATUS_TONE: Record<EStatus, 'neutral' | 'success' | 'warning' | 'danger'> = { active: 'neutral', ready: 'warning', completed: 'success', cancelled: 'danger' }
