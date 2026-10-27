import { ArrowLeft } from 'lucide-react'
import type { ComponentType, ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'

import { colorVars, routeTheme } from '../../lib/navTheme'

/** Sahifa sarlavhasi. Ikonka va rang joriy bo'limdan avtomatik olinadi; `backTo` berilsa "orqaga" havola chiqadi. */
export function PageHeader({
  title,
  subtitle,
  backTo,
  backLabel,
  actions,
  icon,
}: {
  title: string
  subtitle?: string
  backTo?: string
  backLabel?: string
  actions?: ReactNode
  icon?: ComponentType<{ className?: string }>
}) {
  const { pathname } = useLocation()
  const theme = routeTheme(pathname)
  const Icon = icon ?? theme?.icon
  return (
    <div className="rise relative flex flex-col gap-2" style={colorVars(theme?.color ?? 'var(--c-blue)')}>
      <div aria-hidden className="pointer-events-none absolute -left-6 -top-6 h-32 w-80 rounded-full opacity-[0.16] blur-2xl" style={{ background: 'var(--gc)' }} />
      {backTo && (
        <Link to={backTo} className="relative inline-flex w-fit items-center gap-1.5 text-[13px] text-muted transition-colors hover:text-text">
          <ArrowLeft className="size-3.5" />
          {backLabel}
        </Link>
      )}
      <div className="relative flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
        <div className="flex min-w-0 items-center gap-4">
          {Icon && (
            <span className="grid size-12 shrink-0 place-items-center rounded-2xl text-white shadow-[0_6px_16px_-4px_var(--gc)]" style={{ background: 'linear-gradient(135deg, var(--gc), color-mix(in oklab, var(--gc) 65%, #000))' }}>
              <Icon className="size-6" />
            </span>
          )}
          <div className="min-w-0">
            <h1 className="text-[26px] font-semibold leading-tight tracking-[-0.025em]">{title}</h1>
            {subtitle && <p className="mt-0.5 max-w-2xl text-[13px] text-muted">{subtitle}</p>}
          </div>
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </div>
  )
}
