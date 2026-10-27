export type EventKind = 'sos' | 'low_battery' | 'permission_lost' | 'gps_off' | 'signal_lost' | 'signal_back' | 'auto_closed'

export interface Permit {
  employee: { id: number; name: string | null; phone: string | null; has_account: boolean }
  enabled: boolean
  interval_s: number
  window_start: string
  window_end: string
  note: string | null
  consent_at: string | null
  active_session_id: number | null
  exists?: boolean
}

export interface Session {
  id: number
  status: 'active' | 'ended' | 'auto_closed'
  started_at: string
  ended_at: string | null
  distance_km: number
  points_count: number
  last_point_at: string | null
  last_battery: number | null
  end_reason: string | null
  employee?: { id: number; name: string | null }
}

export interface My {
  employee: { id: number; name: string }
  permit: { enabled: boolean; interval_s: number; window_start: string; window_end: string; consent_at: string | null } | null
  session: Session | null
  can_start: boolean
  reason: 'no_permit' | 'consent_required' | 'outside_hours' | null
  privacy: { retention_days: number; only_in_session: boolean }
}

export interface Live {
  session_id: number
  employee: { id: number; name: string | null }
  started_at: string
  lat: number | null
  lng: number | null
  accuracy: number | null
  speed: number | null
  at: string
  battery: number | null
  permission: string | null
  gps_off: boolean
  stale: boolean
  distance_km: number
  open_events: number
}

export interface Ev {
  id: number
  session_id: number | null
  employee: { id: number; name: string | null }
  kind: EventKind
  severity: 'info' | 'warning' | 'critical'
  data: Record<string, unknown> | null
  lat: number | null
  lng: number | null
  created_at: string
  acknowledged_at: string | null
  ack_note: string | null
}

export interface Page<T> {
  total: number
  page: number
  size: number
  items: T[]
}

export const SEV_TONE: Record<Ev['severity'], 'neutral' | 'warning' | 'danger'> = { info: 'neutral', warning: 'warning', critical: 'danger' }
