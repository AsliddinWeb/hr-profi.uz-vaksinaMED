import clsx from 'clsx'
import { useTranslation } from 'react-i18next'
import { NavLink } from 'react-router-dom'

import { useCan } from '../features/auth/useAuth'
import { navById } from '../nav'

/** Bo'lim ichidagi tablar: yon menyuda faqat asosiy band turadi, qolgan sahifalar (yangi qayd, hisobot, ...) shu yerda. */
export function SectionTabs({ ids }: { ids: string[] }) {
  const { i18n } = useTranslation()
  const can = useCan()
  const lang = i18n.language === 'ru' ? 'ru' : 'uz'
  const items = ids
    .map((id) => navById.get(id))
    .filter((it): it is NonNullable<typeof it> => !!it && (!it.permission || can(it.permission)) && (!it.anyPermission || it.anyPermission.some(can)))
  if (items.length < 2) return null
  return (
    <nav className="flex w-fit max-w-full gap-0.5 overflow-x-auto rounded-control bg-(--seg-bg) p-0.5 text-[13px]">
      {items.map((it, i) => {
        const Icon = it.icon
        return (
          <NavLink key={it.id} to={it.to} end={i === 0} className={({ isActive }) => clsx('inline-flex h-8 items-center gap-1.5 whitespace-nowrap rounded-lg px-3.5 transition-colors', isActive ? 'bg-(--seg-on) font-medium text-text shadow-card' : 'text-muted hover:text-text')}>
            {Icon && <Icon className="size-3.5" />}
            {it.label[lang]}
          </NavLink>
        )
      })}
    </nav>
  )
}
