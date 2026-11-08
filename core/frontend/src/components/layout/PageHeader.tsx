import { ArrowLeft, Info, X } from 'lucide-react'
import { useState, type ComponentType, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router-dom'

import { colorVars, routeTheme } from '../../lib/navTheme'
import { infoFor } from '../../lib/processInfo'

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
  const { t, i18n } = useTranslation()
  const lang = i18n.language === 'ru' ? 'ru' : 'uz'
  const theme = routeTheme(pathname)
  const Icon = icon ?? theme?.icon
  const info = infoFor(pathname)
  const [showInfo, setShowInfo] = useState(false)
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
            <h1 className="flex items-center gap-2 text-[26px] font-semibold leading-tight tracking-[-0.025em]">
              {title}
              {info && (
                <button type="button" onClick={() => setShowInfo((v) => !v)} aria-expanded={showInfo} aria-label={t('help.about')} title={t('help.about')} className="grid size-7 place-items-center rounded-full text-muted transition hover:bg-surface-2 hover:text-text">
                  <Info className="size-4" />
                </button>
              )}
            </h1>
            {subtitle && <p className="mt-0.5 max-w-2xl text-[13px] text-muted">{subtitle}</p>}
          </div>
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {info && showInfo && (
        <div className="relative rounded-card border border-border bg-surface p-4 text-[13px] shadow-card">
          <button type="button" onClick={() => setShowInfo(false)} aria-label={t('common.close')} className="absolute right-2 top-2 rounded p-1 text-muted hover:bg-surface-2">
            <X className="size-4" />
          </button>
          <p className="pr-6 font-medium">{info.what[lang]}</p>
          {info.steps && (
            <ol className="mt-2 list-decimal space-y-1 pl-5 text-muted">
              {info.steps[lang].map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ol>
          )}
          <Link to="/help" className="mt-2 inline-block text-xs font-semibold text-primary hover:underline">
            {t('help.allFlows')}
          </Link>
        </div>
      )}
    </div>
  )
}
