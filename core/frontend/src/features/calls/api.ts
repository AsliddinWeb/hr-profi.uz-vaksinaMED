export const STATUS_TONE: Record<string, 'neutral' | 'warning' | 'success' | 'danger'> = {
  ringing: 'warning',
  scheduled: 'warning',
  active: 'success',
  ended: 'neutral',
  declined: 'danger',
  missed: 'danger',
  cancelled: 'neutral',
}

export interface CallPart {
  user_id: number
  name: string | null
  role: 'host' | 'invitee'
  status: 'invited' | 'joined' | 'left' | 'declined' | 'missed'
  first_joined_at: string | null
  left_at: string | null
  seconds: number
}

export interface Call {
  id: number
  kind: 'direct' | 'conference'
  media: 'audio' | 'video'
  title: string | null
  status: string
  host: { id: number; name: string | null } | null
  scheduled_at: string | null
  ring_until: string | null
  started_at: string | null
  ended_at: string | null
  end_reason: string | null
  duration: number | null
  created_at: string
  participants: CallPart[]
  online: number
  me: { role: 'host' | 'invitee'; status: string } | null
  peer: string | null
}

export interface CallDetail extends Call {
  can: { join: boolean; decline: boolean; end: boolean; edit: boolean }
}

export interface CallPage {
  total: number
  page: number
  size: number
  items: Call[]
}

export interface Incoming {
  id: number
  media: 'audio' | 'video'
  caller: string | null
  ring_until: string
}

export interface TokenResp {
  token: string
  url: string | null
  room: string
  identity: string
  media: 'audio' | 'video'
}

export const durationText = (s: number | null): string => {
  if (s === null) return '—'
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}` : `${m}:${String(sec).padStart(2, '0')}`
}

export const callTitle = (c: Call, fallback: string): string => c.title || (c.kind === 'direct' ? (c.peer ?? fallback) : fallback)

/** LiveKit ulanish manzili: sozlamada berilgan yoki o'z domenimizdagi /livekit (gateway). */
export function livekitUrl(tok: TokenResp): string {
  return tok.url || `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/livekit`
}
