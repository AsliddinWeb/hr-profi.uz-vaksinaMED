import type { AttRecord } from '../attendance/api'

export interface FaceStatus {
  employee: { id: number; full_name: string }
  consent: { given: boolean; given_at: string | null; version: string | null; revoked_at: string | null; outdated: boolean }
  current_version: string
  enrolled: boolean
  enrolled_at: string | null
  last_verified_at: string | null
  retention_days: number
}

export interface Challenge {
  id: string
  steps: ('center' | 'left' | 'right')[]
  expires_in: number
  max_frames: number
  min_frames: number
}

export type FaceState = 'enrolled' | 'consent_only' | 'none' | 'revoked'

export interface FaceListItem {
  employee: { id: number; employee_no: number; full_name: string }
  state: FaceState
  consent_version: string | null
  given_at: string | null
  templates: number
  enrolled_at: string | null
  last_verified_at: string | null
}

export interface FaceList {
  total: number
  page: number
  size: number
  summary: { enrolled: number; active: number }
  items: FaceListItem[]
}

export interface FaceDetail {
  employee: { id: number; full_name: string; status: string }
  state: FaceState
  consent: { version: string; given_at: string; revoked_at: string | null } | null
  templates: { id: number; pose: string; model: string; quality: number; created_at: string; last_verified_at: string | null }[]
  verify_ok: number
  verify_fail: number
  attempts: { id: number; purpose: string; success: boolean; liveness_ok: boolean; reason: string | null; created_at: string }[]
}

export interface FaceEvaluation {
  threshold: number
  duplicate_threshold: number
  enrolled_employees: number
  impostor_pairs: number
  genuine_attempts: number
  table: { threshold: number; far: number | null; frr: number | null }[]
  eer_threshold: number | null
  recommended: number | null
  enough_data: boolean
}

export interface FacePunchResult {
  action: 'check_in' | 'check_out'
  record: AttRecord
  score: number
}
