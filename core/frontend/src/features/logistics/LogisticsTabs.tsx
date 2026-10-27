import clsx from 'clsx'
import { useTranslation } from 'react-i18next'
import { NavLink } from 'react-router-dom'

import { useCan } from '../auth/useAuth'

const TABS = [
  { to: '/logistics', key: 'live', end: true },
  { to: '/logistics/vehicles', key: 'vehicles' },
  { to: '/logistics/drivers', key: 'drivers' },
  { to: '/logistics/trips', key: 'trips' },
  { to: '/logistics/fuel', key: 'fuel' },
  { to: '/logistics/reports', key: 'reports' },
]

export function LogisticsTabs() {
  const { t } = useTranslation()
  const can = useCan()
  if (!can('logistics.read') && !can('logistics.manage')) return null
  return (
    <nav className="flex w-fit max-w-full gap-0.5 overflow-x-auto rounded-control bg-(--seg-bg) p-0.5 text-[13px]" aria-label={t('logistics.title')}>
      {TABS.map((x) => (
        <NavLink key={x.to} to={x.to} end={x.end} className={({ isActive }) => clsx('inline-flex h-8 items-center whitespace-nowrap rounded-lg px-3.5 transition-colors', isActive ? 'bg-(--seg-on) font-medium text-text shadow-card' : 'text-muted hover:text-text')}>
          {t(`logistics.tabs.${x.key}`)}
        </NavLink>
      ))}
    </nav>
  )
}
