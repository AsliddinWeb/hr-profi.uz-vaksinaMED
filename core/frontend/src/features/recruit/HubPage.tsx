import { useQuery } from '@tanstack/react-query'
import { BarChart2, Briefcase, ChevronRight, ClipboardList, Columns3, ListChecks, PhoneCall, Users2 } from 'lucide-react'
import type { ComponentType } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { api } from '../../lib/api'
import { useCan } from '../auth/useAuth'
import type { HireRequest } from './RequestsPages'

interface Tile {
  to: string
  icon: ComponentType<{ className?: string }>
  key: string
  stat?: string | null
  tone: string
  show: boolean
}

/** /hub/recruit: Rekruting bo'limining bosh paneli — zayafkadan ishga qabulgacha barcha bo'limlar. */
export function RecruitHubPage() {
  const { t } = useTranslation()
  const can = useCan()
  const staff = can('recruit.read') || can('recruit.manage')
  const reqs = useQuery({ queryKey: ['recruit', 'requests', 'pending'], queryFn: () => api<{ items: HireRequest[] }>('/api/v1/recruit/requests?status=pending') })
  const pending = reqs.data?.items.length
  const tiles: Tile[] = [
    { to: '/recruit/requests', icon: ClipboardList, key: 'requests', stat: pending ? t('rhub.pendingN', { n: pending }) : null, tone: 'from-amber-500 to-orange-600', show: true },
    { to: '/recruit/vacancies', icon: Briefcase, key: 'vacancies', tone: 'from-[#1f3a68] to-[#2a4f8f]', show: staff },
    { to: '/recruit/candidates', icon: Users2, key: 'candidates', tone: 'from-violet-500 to-indigo-600', show: staff },
    { to: '/recruit/requirements', icon: ListChecks, key: 'requirements', tone: 'from-emerald-500 to-teal-600', show: staff },
    { to: '/recruit/recruiter', icon: PhoneCall, key: 'recruiter', tone: 'from-sky-500 to-blue-600', show: staff },
    { to: '/recruit/funnel', icon: BarChart2, key: 'funnel', tone: 'from-rose-500 to-pink-600', show: staff },
    { to: '/recruit/candidates', icon: Columns3, key: 'compare', tone: 'from-slate-500 to-slate-700', show: staff },
  ]
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <section className="rounded-card bg-gradient-to-br from-[#1f3a68] to-[#2a4f8f] p-5 text-white shadow-card">
        <h1 className="text-2xl font-bold">{t('rhub.title')}</h1>
        <p className="mt-1 max-w-2xl text-sm text-white/80">{t('rhub.subtitle')}</p>
      </section>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {tiles
          .filter((x) => x.show)
          .map((x) => (
            <Link key={x.key} to={x.to} className="group flex flex-col gap-3 rounded-card border border-border bg-surface p-4 shadow-card transition hover:-translate-y-0.5 hover:shadow-pop">
              <div className="flex items-center justify-between">
                <span className={`grid size-11 place-items-center rounded-control bg-gradient-to-br text-white ${x.tone}`}>
                  <x.icon className="size-5" />
                </span>
                {x.stat && <span className="rounded-full bg-warning/15 px-2.5 py-1 text-xs font-semibold text-warning">{x.stat}</span>}
              </div>
              <div>
                <div className="flex items-center gap-1 font-semibold">
                  {t(`rhub.${x.key}`)}
                  <ChevronRight className="size-4 text-muted transition group-hover:translate-x-0.5" />
                </div>
                <p className="mt-0.5 text-xs text-muted">{t(`rhub.${x.key}Desc`)}</p>
              </div>
            </Link>
          ))}
      </div>
    </div>
  )
}
