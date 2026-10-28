import { PanelLeftClose, PanelLeftOpen, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, NavLink, useLocation } from 'react-router-dom'

import { BrandLogo } from './BrandLogo'
import { getExtensionNavItems, type NavItem } from '../../extensions/registry'
import { useInboxCount } from '../../features/answers/useInboxCount'
import { useCan } from '../../features/auth/useAuth'
import { useLettersCount } from '../../features/letters/useLettersCount'
import { useMeta } from '../../features/meta/useMeta'
import { useNeedCount } from '../../features/needs/useNeedCount'
import { usePendingPenalties } from '../../features/penalties/usePendingCount'
import { useTaskCount } from '../../features/tasks/useTaskCount'
import { cn } from '../../lib/cn'
import { colorVars, groupColor } from '../../lib/navTheme'
import { coreNav } from '../../nav'

const RAIL_KEY = 'hrprofi.nav.rail'

function load<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key)
    return v ? (JSON.parse(v) as T) : fallback
  } catch {
    return fallback
  }
}
function save(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* storage mavjud emas */
  }
}

interface Section {
  group: string
  items: NavItem[]
}

/** Yon panel: barcha bo'limlar doim ochiq (sarlavha + elementlar), "rail" (faqat ikonkalar) rejimi. */
export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language === 'ru' ? 'ru' : 'uz'
  const { pathname } = useLocation()
  const { data: meta } = useMeta()
  const can = useCan()
  const inbox = useInboxCount()
  const letters = useLettersCount()
  const taskCount = useTaskCount()
  const needCount = useNeedCount()
  const pendingPenalties = usePendingPenalties()
  const [rail, setRail] = useState<boolean>(() => load(RAIL_KEY, false))

  const enabled = (module?: string) => !module || !meta || meta.modules.includes(module)
  const items = [...coreNav, ...getExtensionNavItems()].filter((i) => enabled(i.module) && (!i.permission || can(i.permission)) && (!i.anyPermission || i.anyPermission.some(can)))

  const { main, sections, activeId } = useMemo(() => {
    const main: NavItem[] = []
    const sections: Section[] = []
    for (const it of items) {
      const g = it.group ?? 'main'
      if (g === 'main') main.push(it)
      else {
        const last = sections[sections.length - 1]
        if (last && last.group === g) last.items.push(it)
        else sections.push({ group: g, items: [it] })
      }
    }
    // Eng uzun mos keladigan yo'l = faol element
    const hit = items.filter((i) => pathname === i.to || pathname.startsWith(i.to === '/' ? '/__' : `${i.to}/`)).sort((a, b) => b.to.length - a.to.length)[0]
    return { main, sections, activeId: hit?.id }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items.map((i) => i.id).join('|'), pathname])

  const toggleRail = () =>
    setRail((r) => {
      save(RAIL_KEY, !r)
      return !r
    })

  const badge = (id: string): { n: number; tone: 'danger' | 'neutral' } | null => {
    if (id === 'penalties' && pendingPenalties > 0) return { n: pendingPenalties, tone: 'danger' }
    if (id === 'tasks-board' && taskCount.open > 0) return { n: taskCount.open, tone: taskCount.overdue ? 'danger' : 'neutral' }
    if (id === 'needs' && needCount > 0) return { n: needCount, tone: 'neutral' }
    if (id === 'letters' && letters > 0) return { n: letters, tone: 'danger' }
    if (id === 'answers-inbox' && inbox > 0) return { n: inbox, tone: 'danger' }
    return null
  }

  const link = (it: NavItem, compact: boolean) => {
    const Icon = it.icon
    const b = badge(it.id)
    const active = it.id === activeId
    return (
      <NavLink
        key={it.id}
        to={it.to}
        end
        onClick={onClose}
        title={compact ? it.label[lang] : undefined}
        aria-current={active ? 'page' : undefined}
        style={colorVars(groupColor(it.group))}
        className={cn(
          'group relative flex h-10 items-center gap-3 rounded-[10px] px-1.5 text-sm font-medium transition-colors',
          compact && 'justify-center px-0',
          active ? 'bg-[color-mix(in_oklab,var(--gc)_10%,transparent)] font-semibold text-text' : 'text-text hover:bg-surface-2',
        )}
      >
        {Icon && (
          <span className={cn('grid size-7 shrink-0 place-items-center rounded-lg transition-colors', active ? 'bg-(--gc) text-white shadow-[0_3px_8px_-2px_var(--gc)]' : 'bg-[color-mix(in_oklab,var(--gc)_13%,transparent)] text-(--gc)')} style={colorVars(groupColor(it.group))}>
            <Icon className="size-[17px] stroke-[1.9]" />
          </span>
        )}
        {!compact && <span className="truncate">{it.label[lang]}</span>}
        {b && !compact && (
          <span className={cn('ml-auto rounded-md px-1.5 text-[11px] font-medium tabular-nums', b.tone === 'danger' ? 'bg-danger/12 text-danger' : 'bg-surface-3 text-muted')} aria-label={`${b.n}`}>
            {b.n}
          </span>
        )}
        {b && compact && <span className="absolute right-1 top-1 size-1.5 rounded-full bg-danger" />}
      </NavLink>
    )
  }

  const compact = rail
  return (
    <>
      <div className={cn('fixed inset-0 z-30 bg-black/40 backdrop-blur-[2px] lg:hidden', open ? 'block' : 'hidden')} onClick={onClose} aria-hidden />
      <aside
        aria-label="Navigation"
        className={cn(
          'fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-surface p-2.5 shadow-pop transition-[transform,width] duration-200 lg:sticky lg:top-3 lg:m-3 lg:mr-0 lg:h-[calc(100dvh-1.5rem)] lg:shrink-0 lg:translate-x-0 lg:self-start lg:rounded-[20px] lg:shadow-card',
          compact ? 'lg:w-[68px]' : 'lg:w-60',
          open ? 'translate-x-0' : '-translate-x-full max-lg:shadow-none',
        )}
      >
        <div className={cn('flex items-center gap-2 px-1.5 pb-4 pt-1.5', compact ? 'lg:flex-col lg:px-0' : 'justify-between')}>
          <Link to="/" onClick={onClose} className="flex min-w-0 items-center" aria-label={meta?.brand.name ?? 'HR-Profi'}>
            {compact ? <img src="/logo-mark.png" alt={meta?.brand.name ?? 'HR-Profi'} className="h-8 w-auto dark:rounded-md dark:bg-white dark:p-0.5" /> : <BrandLogo src={meta?.brand.logo} alt={meta?.brand.name ?? 'HR-Profi'} className="h-9 w-auto max-w-full" />}
          </Link>
          <button className="hidden size-7 cursor-pointer place-items-center rounded-md text-muted transition-colors hover:bg-surface-2 hover:text-text lg:grid" onClick={toggleRail} aria-label={compact ? 'Expand' : 'Collapse'} title={compact ? 'Expand' : 'Collapse'}>
            {compact ? <PanelLeftOpen className="size-4" /> : <PanelLeftClose className="size-4" />}
          </button>
          <button className="grid size-8 cursor-pointer place-items-center rounded-md text-muted hover:bg-surface-2 lg:hidden" onClick={onClose} aria-label="Close">
            <X className="size-4" />
          </button>
        </div>

        <nav className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto overflow-x-hidden pb-2">
          <div className="flex flex-col gap-0.5 pb-1">{main.map((it) => link(it, compact))}</div>
          {sections.map((s) => {
            if (compact) {
              return (
                <div key={s.group} className="mt-1.5 flex flex-col gap-0.5 border-t border-border pt-1.5">
                  {s.items.map((it) => link(it, true))}
                </div>
              )
            }
            return (
              <div key={s.group} className="mt-4">
                <div className="mb-1 truncate px-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted">{t(`nav.group.${s.group}`)}</div>
                <div className="flex flex-col gap-0.5">{s.items.map((it) => link(it, false))}</div>
              </div>
            )
          })}
        </nav>
      </aside>
    </>
  )
}
