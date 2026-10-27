import { useTranslation } from 'react-i18next'
import { NavLink } from 'react-router-dom'

import { useCan } from '../auth/useAuth'

/** Hisobotlar markazi bo'limlari. */
export function ReportsTabs() {
  const { t } = useTranslation()
  const manage = useCan()('reports.manage')
  const tabs = [
    { to: '/reports', end: true, label: t('reports.tabs.create') },
    { to: '/reports/history', end: false, label: t('reports.tabs.history') },
    ...(manage ? [{ to: '/reports/schedules', end: false, label: t('reports.tabs.schedules') }] : []),
  ]
  return (
    <nav className="flex w-fit max-w-full gap-0.5 overflow-x-auto rounded-control bg-(--seg-bg) p-0.5 text-[13px]" aria-label={t('reports.title')}>
      {tabs.map((x) => (
        <NavLink key={x.to} to={x.to} end={x.end} className={({ isActive }) => 'inline-flex h-8 items-center whitespace-nowrap rounded-lg px-3.5 transition-colors ' + (isActive ? 'bg-(--seg-on) font-medium text-text shadow-card' : 'text-muted hover:text-text')}>
          {x.label}
        </NavLink>
      ))}
    </nav>
  )
}
