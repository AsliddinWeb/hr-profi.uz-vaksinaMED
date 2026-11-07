import type { Incident, LetterStatus } from './api'

export interface AutoStep {
  step: number
  label: string
  amount: number
  block_days: number
}

export interface AutoFacts {
  incident: Incident
  incident_label: string
  date: string
  employee: string
  employee_phone: string | null
  position: string | null
  department: string | null
  branch: string | null
  branch_phone: string | null
  coordinator: string | null
  coordinator_phone: string | null
  shift: string | null
  planned_start: string | null
  planned_end: string | null
  check_in: string | null
  check_out: string | null
  late_minutes: number
  early_minutes: number
  month_count: number
  step: number
  measure: string
  amount: number
  next_step: number | null
  next_measure: string | null
  next_amount: number | null
  steps: AutoStep[]
}

export interface AutoDocument {
  recipient: string
  company: string
  title: string
  subtitle: string
  measure_line: string
  preamble: string
  intro: string
  incident: string
  basis: string | null
  explanation: string | null
  explanation_lead: string
  measure: string
  escalation: string
  next: string | null
  closing: string
  steps: AutoStep[]
  step: number
}

export interface AutoLetter {
  id: number
  number: string
  code: string
  status: LetterStatus
  incident_type: Incident
  incident_date: string
  facts: AutoFacts
  explanation: string | null
  confirmed_at: string | null
  submitted_at: string | null
  signature_image: string | null
  review_note: string | null
  signer: string
  verify_url: string | null
  document: AutoDocument
  min_words: number
  min_chars: number
}

/** Boshqa sahifadan (masalan davomatda «Keldim» bloklanganda) oynani ochish. */
export const OPEN_EVENT = 'auto-letter:open'
export const openAutoLetter = () => window.dispatchEvent(new Event(OPEN_EVENT))

export const money = (n: number) => `${Math.round(n).toLocaleString('ru-RU').replace(/ /g, ' ')} so'm`

export function wordCount(s: string) {
  const t = s.trim()
  return t ? t.split(/\s+/).length : 0
}

export function shortName(full: string) {
  const [last, first] = full.trim().split(/\s+/)
  return first ? `${last} ${first[0]}.` : last
}

export function tashkentTime(iso: string) {
  const d = new Date(iso)
  const date = new Intl.DateTimeFormat('ru-RU', { timeZone: 'Asia/Tashkent', day: '2-digit', month: '2-digit', year: 'numeric' }).format(d)
  const time = new Intl.DateTimeFormat('ru-RU', { timeZone: 'Asia/Tashkent', hour: '2-digit', minute: '2-digit' }).format(d)
  return { date, time }
}
