import clsx from 'clsx'
import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router-dom'

import { useCan } from '../features/auth/useAuth'
import { clusterOf, matchNav, navById } from '../nav'

const ALL = [...navById.values()]

/** Bo'lim tablari: yon menyuda faqat asosiy band turadi, qolgan sahifalar shu yerda (nav.ts NAV_CLUSTERS). */
export function ClusterTabs() {
  const { pathname } = useLocation()
  const { i18n } = useTranslation()
  const can = useCan()
  const hit = matchNav(pathname, ALL)
  const cluster = hit && clusterOf.get(hit.id)
  if (!hit || !cluster || cluster.tabs === false) return null
  const lang = i18n.language === 'ru' ? 'ru' : 'uz'
  const items = cluster.ids
    .map((id) => navById.get(id))
    .filter((it): it is NonNullable<typeof it> => !!it && (!it.permission || can(it.permission)) && (!it.anyPermission || it.anyPermission.some(can)))
  if (items.length < 2) return null
  return (
    <nav className="mb-3 flex w-fit max-w-full gap-0.5 overflow-x-auto rounded-control bg-(--seg-bg) p-0.5 text-[13px]">
      {items.map((it) => {
        const Icon = it.icon
        const active = it.id === hit.id
        return (
          <Link key={it.id} to={it.to} aria-current={active ? 'page' : undefined} className={clsx('inline-flex h-8 items-center gap-1.5 whitespace-nowrap rounded-lg px-3.5 transition-colors', active ? 'bg-(--seg-on) font-medium text-text shadow-card' : 'text-muted hover:text-text')}>
            {Icon && <Icon className="size-3.5" />}
            {it.label[lang]}
          </Link>
        )
      })}
    </nav>
  )
}
