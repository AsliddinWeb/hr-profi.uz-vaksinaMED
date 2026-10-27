import { CalendarDays, KanbanSquare, List, Plus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, NavLink } from 'react-router-dom'

import { Button } from '../../components/ui/Button'

/** Kanban / ro'yxat / kalendar ko'rinishlari orasida o'tish va "yangi topshiriq". */
export function ViewTabs() {
  const { t } = useTranslation()
  const items = [
    { to: '/tasks/board', icon: KanbanSquare, label: t('tasks.views.board') },
    { to: '/tasks', icon: List, label: t('tasks.views.list'), end: true },
    { to: '/tasks/calendar', icon: CalendarDays, label: t('tasks.views.calendar') },
  ]
  return (
    <div className="flex flex-wrap items-center gap-2">
      <nav className="flex rounded-control bg-(--seg-bg) p-0.5 text-[13px]" aria-label={t('tasks.views.label')}>
        {items.map(({ to, icon: Icon, label, end }) => (
          <NavLink key={to} to={to} end={end} className={({ isActive }) => 'inline-flex items-center gap-1.5 rounded-[10px] px-3 py-1.5 ' + (isActive ? 'bg-primary text-primary-fg' : 'text-muted hover:text-text')}>
            <Icon className="size-4" />
            {label}
          </NavLink>
        ))}
      </nav>
      <Link to="/tasks/new">
        <Button>
          <Plus className="size-4" />
          {t('tasks.new')}
        </Button>
      </Link>
    </div>
  )
}
