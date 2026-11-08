export type Audience = 'all' | 'students' | 'staff'

export interface Question {
  id: string
  text: string
  options: string[]
  correct?: number[]
  multiple?: boolean
}

export interface Media {
  video: { kind: 'youtube' | 'drive' | 'link' | null; id: string | null; url: string | null; thumb: string | null; embed: string | null }
  slides: { id: string | null; url: string | null; embed: string | null }
}

export interface Stage {
  id: number
  program_id: number
  position: number
  kind: string
  title: string
  description: string | null
  url: string | null
  slides_url: string | null
  audience: Audience
  published: boolean
  pass_score: number | null
  max_attempts: number
  min_video_seconds: number | null
  min_slides_seconds: number | null
  questions: Question[]
  question_count: number
  media: Media
}

export interface Monitoring {
  camera: boolean
  live: boolean
  record: boolean
  snapshots: boolean
}

export interface Track {
  id: number
  name: string
  description: string | null
  pass_score: number
  position: { id: number; name: string } | null
  monitoring: Monitoring
  enrolled: number
  stages: Stage[]
}

export interface Req {
  video?: { need: number; seen: number; duration: number | null; done: boolean }
  slides?: { need: number; seen: number; done: boolean }
  test?: { threshold: number; score: number | null; attempts: number; max_attempts: number; done: boolean }
}

export type StageState = 'done' | 'available' | 'locked'

export interface MyStage extends Stage {
  state: StageState
  score: number | null
  attempts: number
  req: Req
}

export interface MyData {
  me: { full_name: string; phone: string | null; position: string | null; branch: string | null; branch_address: string | null; mentor: string | null; mentor_phone: string | null; hire_date: string | null; photo: boolean; employee_id: number }
  enrollment: { id: number; status: string; started_at: string; due_date: string | null; consent: string | null }
  program: { id: number; name: string; description: string | null; position: string | null; pass_score: number }
  monitoring: Monitoring
  livekit: boolean
  summary: { required: number; done: number; percent: number; avg_score: number | null }
  stages: MyStage[]
}

export interface Session {
  id: number
  step_id: number | null
  step: string | null
  started_at: string
  last_seen_at: string
  ended_at: string | null
  live: boolean
  clips: number
  snapshots: number
  seconds: number
  events: { at: string; kind: string }[]
}

export interface ResultRow {
  id: number
  employee: { id: number; full_name: string } | null
  status: string
  started_at: string
  consent: string | null
  summary: { required: number; done: number; percent: number; avg_score: number | null }
  stages: { id: number; title: string; state: StageState; req: Req }[]
  sessions: Session[]
  live: boolean
}

export interface LiveToken {
  token: string
  url: string | null
  room: string
}

export const livekitUrl = (t: LiveToken) => t.url || `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/livekit`

export const fmtSec = (s: number) => {
  const m = Math.floor(s / 60)
  return `${m}:${String(Math.floor(s % 60)).padStart(2, '0')}`
}
