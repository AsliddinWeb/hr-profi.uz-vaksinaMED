import { useQueryClient } from '@tanstack/react-query'
import { ChevronRight, Menu, Moon, Search, Sun } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation, useNavigate } from 'react-router-dom'

import type { Me } from '../../features/auth/useAuth'
import { NotificationBell } from '../../features/notifications/NotificationBell'
import { send } from '../../lib/api'
import { cn } from '../../lib/cn'
import { colorVars, routeTheme } from '../../lib/navTheme'
import { setLang } from '../../lib/i18n'
import { getTheme, resolveTheme, toggleTheme } from '../../lib/theme'
import { Button } from '../ui/Button'
import { UserMenu } from './UserMenu'

export function Topbar({ onMenu }: { onMenu: () => void }) {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const { pathname } = useLocation()
  const theme = routeTheme(pathname)
  const lang = i18n.language === 'ru' ? 'ru' : 'uz'
  const inputRef = useRef<HTMLInputElement>(null)
  const mac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform)
  const [dark, setDark] = useState(() => resolveTheme(getTheme()) === 'dark')

  // Cmd/Ctrl+K — qidiruvga o'tish
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        inputRef.current?.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  const changeLang = (l: 'uz' | 'ru') => {
    setLang(l)
    // Tanlangan tilni profilga ham saqlaymiz (kirgan bo'lsa)
    if (qc.getQueryData<Me | null>(['me'])) {
      qc.setQueryData<Me | null>(['me'], (m) => (m ? { ...m, locale: l } : m))
      void send('PATCH', '/api/auth/me', { locale: l }).catch(() => {})
    }
  }

  const Icon = theme?.icon
  const iconBtn = 'relative grid size-10 cursor-pointer place-items-center rounded-xl bg-surface shadow-card transition-all hover:-translate-y-px hover:shadow-pop'

  return (
    <header className="sticky top-0 z-20 flex items-center gap-3 bg-bg/80 px-4 py-3 backdrop-blur-md lg:px-8">
      <Button variant="ghost" className="size-10 bg-surface px-0 shadow-card lg:hidden" onClick={onMenu} aria-label={t('app.menu')}>
        <Menu />
      </Button>

      {theme?.label && (
        <div className="hidden min-w-0 items-center gap-2 text-[13px] xl:flex" style={colorVars(theme.color)}>
          {Icon && (
            <span className="grid size-6 place-items-center rounded-md bg-[color-mix(in_oklab,var(--gc)_15%,transparent)] text-(--gc)">
              <Icon className="size-3.5" />
            </span>
          )}
          {theme.group && theme.group !== 'main' && (
            <>
              <span className="text-muted">{t(`nav.group.${theme.group}`)}</span>
              <ChevronRight className="size-3.5 text-muted/60" />
            </>
          )}
          <span className="truncate font-semibold">{theme.label[lang]}</span>
        </div>
      )}

      <form
        role="search"
        className="relative ml-auto hidden w-full max-w-sm flex-1 sm:block"
        onSubmit={(e) => {
          e.preventDefault()
          const v = query.trim()
          if (v.length >= 2) navigate(`/search?q=${encodeURIComponent(v)}`)
        }}
      >
        <Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted" />
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t('app.search')}
          aria-label={t('app.search')}
          className="h-10 w-full rounded-xl bg-surface pl-10 pr-14 text-[13px] shadow-card outline-none transition-shadow placeholder:text-muted hover:shadow-[inset_0_0_0_1px_var(--border-strong)] focus:shadow-[inset_0_0_0_1px_var(--primary),0_0_0_3px_var(--ring)]"
        />
        <kbd className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 rounded-md bg-surface-3 px-1.5 py-0.5 font-mono text-[10px] text-muted">{mac ? '⌘K' : 'Ctrl K'}</kbd>
      </form>

      <div className="ml-auto flex items-center gap-2 sm:ml-0">
        <div className="flex h-10 items-center rounded-xl bg-surface p-1 text-xs font-semibold shadow-card" role="group" aria-label="Language">
          {(['uz', 'ru'] as const).map((l) => (
            <button
              key={l}
              onClick={() => changeLang(l)}
              aria-pressed={i18n.language === l}
              className={cn('h-8 rounded-lg px-2.5 transition-colors', i18n.language === l ? 'bg-primary text-primary-fg shadow-[0_2px_6px_-1px_color-mix(in_oklab,var(--primary)_55%,transparent)]' : 'text-muted hover:text-text')}
            >
              {l.toUpperCase()}
            </button>
          ))}
        </div>
        <button className={iconBtn} aria-label={t('theme.toggle')} onClick={() => setDark(toggleTheme() === 'dark')}>
          {dark ? <Sun className="size-[18px] text-(--c-amber)" /> : <Moon className="size-[18px] text-(--c-indigo)" />}
        </button>
        <NotificationBell />
        <UserMenu />
      </div>
    </header>
  )
}
