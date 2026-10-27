export const PERIODS = ['yesterday', 'last_7d', 'last_week', 'this_month', 'last_month'] as const
export type Period = (typeof PERIODS)[number]

export interface ReportType {
  type: string
  title: { uz: string; ru: string }
  needs_period: boolean
}

export interface Run {
  id: number
  type: string
  start: string | null
  end: string | null
  format: 'xlsx' | 'pdf'
  lang: 'uz' | 'ru'
  status: 'ok' | 'failed'
  error: string | null
  filename: string | null
  size: number
  rows: number
  created_at: string
  schedule: { id: number; name: string | null } | null
  created_by: string | null
}

export interface RunPage {
  total: number
  page: number
  size: number
  items: Run[]
}

export interface Schedule {
  id: number
  name: string
  report_type: string
  period: Period
  format: 'xlsx' | 'pdf'
  lang: 'uz' | 'ru'
  frequency: 'daily' | 'weekly' | 'monthly'
  hour: number
  minute: number
  weekday: number | null
  month_day: number | null
  channels: string[]
  is_active: boolean
  last_run_at: string | null
  next_run_at: string | null
  last_status: 'ok' | 'failed' | null
  recipients: { id: number; name: string | null; telegram: boolean }[]
}

export const fileUrl = (id: number) => `/api/v1/reports/runs/${id}/file`
export const sizeKb = (b: number) => (b < 1024 * 1024 ? `${Math.max(1, Math.round(b / 1024))} KB` : `${(b / 1024 / 1024).toFixed(1)} MB`)

export function whenText(t: (k: string, o?: Record<string, unknown>) => string, s: Pick<Schedule, 'frequency' | 'weekday' | 'month_day' | 'hour' | 'minute'>): string {
  const time = `${String(s.hour).padStart(2, '0')}:${String(s.minute).padStart(2, '0')}`
  if (s.frequency === 'daily') return t('reports.schedules.daily', { time })
  if (s.frequency === 'weekly') return t('reports.schedules.weekly', { day: t(`reports.weekday.${s.weekday ?? 0}`), time })
  return t('reports.schedules.monthly', { day: s.month_day, time })
}
