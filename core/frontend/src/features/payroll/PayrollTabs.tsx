import clsx from 'clsx'
import { useTranslation } from 'react-i18next'
import { NavLink } from 'react-router-dom'

import { useCan } from '../auth/useAuth'

const TABS = [
  { to: '/payroll', key: 'runs', end: true },
  { to: '/payroll/schemes', key: 'schemes' },
  { to: '/payroll/items', key: 'items' },
]

export function PayrollTabs() {
  const { t } = useTranslation()
  const can = useCan()
  if (!can('payroll.read')) return null
  return (
    <nav className="flex w-fit max-w-full gap-0.5 overflow-x-auto rounded-control bg-(--seg-bg) p-0.5 text-[13px]" aria-label={t('payroll.title')}>
      {TABS.map((x) => (
        <NavLink key={x.to} to={x.to} end={x.end} className={({ isActive }) => clsx('inline-flex h-8 items-center whitespace-nowrap rounded-lg px-3.5 transition-colors', isActive ? 'bg-(--seg-on) font-medium text-text shadow-card' : 'text-muted hover:text-text')}>
          {t(`payroll.tabs.${x.key}`)}
        </NavLink>
      ))}
    </nav>
  )
}
