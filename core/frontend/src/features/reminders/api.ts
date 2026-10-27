export const REPEATS = ['once', 'daily', 'weekly', 'monthly', 'yearly'] as const
export type Repeat = (typeof REPEATS)[number]

export interface Reminder {
  id: number
  title: string
  note: string | null
  link: string | null
  owner_id: number
  recipients: { id: number; name: string | null }[]
  repeat: Repeat
  interval: number
  weekdays: number[]
  first_at: string
  until: string | null
  telegram: boolean
  is_active: boolean
  next_at: string | null
  snooze_at: string | null
  last_fired_at: string | null
  last_ack_at: string | null
  fire_count: number
  finished: boolean
}

export interface ReminderDetail extends Reminder {
  is_owner: boolean
  next_five: string[]
  events: { id: number; action: string; data: Record<string, unknown> | null; created_at: string }[]
}

export interface ReminderPage {
  total: number
  page: number
  size: number
  items: Reminder[]
}

export interface UpcomingItem {
  reminder_id: number
  title: string
  at: string
  repeat: string
}

export function whenText(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Tashkent' }).format(new Date(iso))
}

export function timeText(iso: string): string {
  return new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Tashkent' }).format(new Date(iso))
}

export function dayText(iso: string): string {
  return new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: '2-digit', timeZone: 'Asia/Tashkent' }).format(new Date(iso))
}
