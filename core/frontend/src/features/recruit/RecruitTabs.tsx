import clsx from 'clsx'
import { useTranslation } from 'react-i18next'
import { NavLink } from 'react-router-dom'

const TABS = [
  { to: '/recruit/vacancies', key: 'vacancies' },
  { to: '/recruit/candidates', key: 'candidates' },
  { to: '/recruit/applications', key: 'applications' },
  { to: '/recruit/recruiter', key: 'recruiter' },
  { to: '/recruit/sources', key: 'sources' },
  { to: '/recruit/requirements', key: 'requirements' },
  { to: '/recruit/summary', key: 'summary' },
]

export function RecruitTabs() {
  const { t } = useTranslation()
  return (
    <nav className="flex w-fit max-w-full gap-0.5 overflow-x-auto rounded-control bg-(--seg-bg) p-0.5 text-[13px]" aria-label={t('recruit.title')}>
      {TABS.map((x) => (
        <NavLink key={x.to} to={x.to} className={({ isActive }) => clsx('inline-flex h-8 items-center whitespace-nowrap rounded-lg px-3.5 transition-colors', isActive ? 'bg-(--seg-on) font-medium text-text shadow-card' : 'text-muted hover:text-text')}>
          {t(`recruit.tabs.${x.key}`)}
        </NavLink>
      ))}
    </nav>
  )
}
