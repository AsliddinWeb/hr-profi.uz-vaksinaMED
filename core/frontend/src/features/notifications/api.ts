export interface NotificationItem {
  id: number
  kind: string
  severity: 'info' | 'success' | 'warning' | 'danger'
  title: { uz: string; ru: string }
  body: { uz: string | null; ru: string | null }
  link: string | null
  created_at: string
  read: boolean
}

export interface NotificationPage {
  total: number
  page: number
  size: number
  items: NotificationItem[]
}

export const pick = <T extends { uz: string | null; ru: string | null }>(v: T, lang: string) =>
  (lang === 'ru' ? v.ru : v.uz) ?? v.uz
