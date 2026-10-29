import type { ComponentType } from 'react'

import { getExtensionNavItems, type NavItem } from '../extensions/registry'
import { coreNav } from '../nav'

export type GroupKey = NonNullable<NavItem['group']>

/** Modul guruhi -> palitra rangi (tokens.css dagi --c-*). */
const COLORS: Record<GroupKey, string> = {
  main: 'blue',
  people: 'blue',
  org: 'indigo',
  hr: 'rose',
  schedule: 'violet',
  attendance: 'teal',
  requests: 'amber',
  tasks: 'indigo',
  needs: 'orange',
  checklists: 'green',
  recruit: 'rose',
  internship: 'violet',
  payroll: 'green',
  canteen: 'orange',
  logistics: 'teal',
  warehouse: 'amber',
  mobile: 'blue',
  reception: 'rose',
  helpdesk: 'indigo',
  calls: 'green',
  ai: 'violet',
  reports: 'blue',
  migration: 'amber',
  pharmacy: 'green',
  admin: 'slate',
  system: 'slate',
}

export const groupColor = (g: GroupKey | undefined): string => `var(--c-${COLORS[g ?? 'main']})`

export interface RouteTheme {
  label?: Record<'uz' | 'ru', string>
  icon?: ComponentType<{ className?: string }>
  color: string
  group?: GroupKey
}

/** Joriy yo'lga eng mos nav elementi (eng uzun mos prefiks) — sarlavha ikonkasi va rangi shundan olinadi. */
export function routeTheme(pathname: string): RouteTheme | null {
  const hit = [...coreNav, ...getExtensionNavItems()]
    .filter((i) => pathname === i.to || pathname.startsWith(i.to === '/' ? '/__' : `${i.to}/`))
    .sort((a, b) => b.to.length - a.to.length)[0]
  return hit ? { label: hit.label, icon: hit.icon, color: groupColor(hit.group), group: hit.group } : null
}

/** Tint fon + rang uchun inline CSS o'zgaruvchisi. */
export const colorVars = (color: string) => ({ ['--gc' as string]: color }) as React.CSSProperties
