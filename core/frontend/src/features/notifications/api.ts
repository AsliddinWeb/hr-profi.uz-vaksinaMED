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

export interface PrefsResponse {
  categories: { key: string; mandatory: boolean; muted: boolean; unread: number }[]
}

export const catKey = (kind: string) => kind.split('.')[0]

/** Toifa nomi: tarjima bo'lmasa kalitning o'zi ko'rsatiladi. */
export const catLabel = (t: (k: string, o?: Record<string, unknown>) => string, key: string) => t(`notifications.cat.${key}`, { defaultValue: key })
