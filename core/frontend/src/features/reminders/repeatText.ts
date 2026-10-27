import type { TFunction } from 'i18next'

import { timeText, type Reminder } from './api'

/** "Har kuni 09:00", "Har 2 haftada: Du, Ch 09:00" kabi qisqa tavsif. */
export function repeatText(t: TFunction, r: Pick<Reminder, 'repeat' | 'interval' | 'weekdays' | 'first_at' | 'until'>): string {
  const time = timeText(r.first_at)
  const until = r.until ? ` · ${t('reminders.until', { date: r.until.split('-').reverse().join('.') })}` : ''
  if (r.repeat === 'once') return t('reminders.summary.once') + until
  const days = r.repeat === 'weekly' && r.weekdays.length ? `: ${r.weekdays.map((d) => t(`schedule.wd.${d}`)).join(', ')}` : ''
  return `${t(`reminders.summary.${r.repeat}`, { count: r.interval })}${days} ${time}${until}`
}
