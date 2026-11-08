import { useQuery } from '@tanstack/react-query'
import { BookOpen, CalendarRange, ChevronRight, ClipboardCheck, GraduationCap, MonitorPlay, PlayCircle, Radio } from 'lucide-react'
import type { ComponentType } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { api } from '../../lib/api'
import { useCan } from '../auth/useAuth'
import type { MyData, Track } from './api'

interface Tile {
  to: string
  icon: ComponentType<{ className?: string }>
  title: string
  desc: string
  stat?: string | null
  tone: string
  show: boolean
}

/** /hub/preboarding: Prebording bo'limining bosh paneli — barcha bo'limlar kartochka ko'rinishida, asosiy raqamlar bilan. */
export function PreboardingHubPage() {
  const { t } = useTranslation()
  const can = useCan()
  const staff = can('internship.read') || can('internship.manage')
  const tracks = useQuery({ queryKey: ['preboarding', 'tracks'], queryFn: () => api<{ items: Track[] }>('/api/v1/preboarding/tracks'), enabled: staff })
  const my = useQuery({ queryKey: ['preboarding', 'my'], queryFn: () => api<MyData | null>('/api/v1/preboarding/my'), enabled: can('internship.own') })
  const interns = (tracks.data?.items ?? []).reduce((a, x) => a + x.enrolled, 0)
  const own = can('internship.own') || staff
  const tiles: Tile[] = [
    { to: '/preboarding/my', icon: PlayCircle, title: t('preboarding.hub.my'), desc: t('preboarding.hub.myDesc'), stat: my.data ? `${my.data.summary.done}/${my.data.summary.required}` : null, tone: 'from-emerald-500 to-teal-600', show: !!my.data },
    { to: '/preboarding', icon: MonitorPlay, title: t('preboarding.hub.lessons'), desc: t('preboarding.hub.lessonsDesc'), stat: tracks.data ? t('preboarding.hub.tracksN', { n: tracks.data.items.length, i: interns }) : null, tone: 'from-[#1f3a68] to-[#2a4f8f]', show: staff },
    { to: '/internship', icon: GraduationCap, title: t('preboarding.hub.internship'), desc: t('preboarding.hub.internshipDesc'), tone: 'from-violet-500 to-indigo-600', show: own },
    { to: '/internship/classes', icon: CalendarRange, title: t('preboarding.hub.classes'), desc: t('preboarding.hub.classesDesc'), tone: 'from-sky-500 to-blue-600', show: own },
    { to: '/attestation', icon: ClipboardCheck, title: t('preboarding.hub.attestation'), desc: t('preboarding.hub.attestationDesc'), tone: 'from-amber-500 to-orange-600', show: can('attestation.own') || can('attestation.read') || can('attestation.manage') },
    { to: '/internship/programs', icon: BookOpen, title: t('preboarding.hub.programs'), desc: t('preboarding.hub.programsDesc'), tone: 'from-rose-500 to-pink-600', show: own },
  ]
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <section className="rounded-card bg-gradient-to-br from-[#1f3a68] to-[#2a4f8f] p-5 text-white shadow-card">
        <h1 className="text-2xl font-bold">{t('preboarding.hub.title')}</h1>
        <p className="mt-1 max-w-2xl text-sm text-white/80">{t('preboarding.hub.subtitle')}</p>
      </section>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {tiles
          .filter((x) => x.show)
          .map((x) => (
            <Link key={x.to} to={x.to} className="group flex flex-col gap-3 rounded-card border border-border bg-surface p-4 shadow-card transition hover:-translate-y-0.5 hover:shadow-pop">
              <div className="flex items-center justify-between">
                <span className={`grid size-11 place-items-center rounded-control bg-gradient-to-br text-white ${x.tone}`}>
                  <x.icon className="size-5" />
                </span>
                {x.stat && <span className="rounded-full bg-surface-2 px-2.5 py-1 text-xs font-semibold tabular-nums">{x.stat}</span>}
              </div>
              <div>
                <div className="flex items-center gap-1 font-semibold">
                  {x.title}
                  <ChevronRight className="size-4 text-muted transition group-hover:translate-x-0.5" />
                </div>
                <p className="mt-0.5 text-xs text-muted">{x.desc}</p>
              </div>
            </Link>
          ))}
      </div>
      {staff && (
        <p className="flex items-center gap-1.5 text-xs text-muted">
          <Radio className="size-3.5" />
          {t('preboarding.hub.liveHint')}
        </p>
      )}
    </div>
  )
}
