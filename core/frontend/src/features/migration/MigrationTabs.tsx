import { useTranslation } from 'react-i18next'
import { NavLink } from 'react-router-dom'

export function MigrationTabs() {
  const { t } = useTranslation()
  const tabs = [
    { to: '/migration', end: true, label: t('migration.tabs.batches') },
    { to: '/migration/reconcile', end: false, label: t('migration.tabs.reconcile') },
    { to: '/migration/templates', end: false, label: t('migration.tabs.templates') },
  ]
  return (
    <nav className="flex w-fit max-w-full gap-0.5 overflow-x-auto rounded-control bg-(--seg-bg) p-0.5 text-[13px]" aria-label={t('migration.title')}>
      {tabs.map((x) => (
        <NavLink key={x.to} to={x.to} end={x.end} className={({ isActive }) => 'inline-flex h-8 items-center whitespace-nowrap rounded-lg px-3.5 transition-colors ' + (isActive ? 'bg-(--seg-on) font-medium text-text shadow-card' : 'text-muted hover:text-text')}>
          {x.label}
        </NavLink>
      ))}
    </nav>
  )
}
