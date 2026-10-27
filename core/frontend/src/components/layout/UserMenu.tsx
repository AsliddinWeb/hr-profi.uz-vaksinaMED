import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Bell, ChevronDown, LogOut, UserRound } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'

import { useMe } from '../../features/auth/useAuth'
import { send } from '../../lib/api'
import { initials } from '../../lib/format'

export function UserMenu() {
  const { t, i18n } = useTranslation()
  const { data: me } = useMe()
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false)
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const logout = useMutation({
    mutationFn: () => send('POST', '/api/auth/logout'),
    onSettled: () => {
      qc.clear()
      navigate('/login', { replace: true })
    },
  })

  if (!me) return null
  const role = i18n.language === 'ru' ? me.role.name_ru : me.role.name_uz

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex h-10 cursor-pointer items-center gap-2.5 rounded-xl bg-surface pl-1 pr-2.5 shadow-card transition-all hover:-translate-y-px hover:shadow-pop"
      >
        <span className="grid size-8 place-items-center rounded-[10px] bg-[linear-gradient(135deg,var(--c-blue),var(--c-violet))] text-[11px] font-semibold text-white">{initials(me.full_name)}</span>
        <span className="hidden min-w-0 text-left leading-tight md:block">
          <span className="block max-w-36 truncate text-[13px] font-semibold">{me.full_name}</span>
          <span className="block max-w-36 truncate text-[11px] text-muted">{role}</span>
        </span>
        <ChevronDown className={'hidden size-3.5 text-muted transition-transform md:block ' + (open ? 'rotate-180' : '')} />
      </button>
      {open && (
        <div role="menu" className="rise absolute right-0 z-30 mt-2 w-80 rounded-2xl bg-surface p-2 shadow-pop">
          <div className="flex items-center gap-3.5 rounded-xl bg-surface-2 p-3.5">
            <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-[linear-gradient(135deg,var(--c-blue),var(--c-violet))] text-base font-semibold text-white">{initials(me.full_name)}</span>
            <div className="min-w-0">
              <div className="truncate text-[15px] font-semibold">{me.full_name}</div>
              <div className="mt-0.5 text-[13px] text-muted">{role}</div>
              <div className="font-mono text-xs text-muted">@{me.login}</div>
            </div>
          </div>
          <div className="mt-2 flex flex-col gap-0.5">
            <Link role="menuitem" to="/profile" onClick={() => setOpen(false)} className="flex h-11 cursor-pointer items-center gap-3 rounded-xl px-2.5 text-sm font-medium transition-colors hover:bg-surface-2">
              <span className="grid size-8 place-items-center rounded-lg bg-[color-mix(in_oklab,var(--c-blue)_14%,transparent)] text-(--c-blue)">
                <UserRound className="size-[18px]" />
              </span>
              {t('profile.title')}
            </Link>
            <Link role="menuitem" to="/notifications" onClick={() => setOpen(false)} className="flex h-11 cursor-pointer items-center gap-3 rounded-xl px-2.5 text-sm font-medium transition-colors hover:bg-surface-2">
              <span className="grid size-8 place-items-center rounded-lg bg-[color-mix(in_oklab,var(--c-amber)_16%,transparent)] text-(--c-amber)">
                <Bell className="size-[18px]" />
              </span>
              {t('notifications.title')}
            </Link>
          </div>
          <div className="my-2 h-px bg-border" />
          <button role="menuitem" onClick={() => logout.mutate()} className="flex h-11 w-full cursor-pointer items-center gap-3 rounded-xl px-2.5 text-left text-sm font-medium text-danger transition-colors hover:bg-danger/10">
            <span className="grid size-8 place-items-center rounded-lg bg-danger/12">
              <LogOut className="size-[18px]" />
            </span>
            {t('auth.logout')}
          </button>
        </div>
      )}
    </div>
  )
}
