import { useQuery } from '@tanstack/react-query'
import { AlarmClock, ArrowRight, BellRing, CalendarCheck2, CheckCheck, FileSignature, Gavel, Inbox, ListTodo, PackagePlus, UserX } from 'lucide-react'
import { useMemo, type ComponentType } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { TeamArt } from '../../components/illustrations'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { getExtensionNavItems, type NavItem } from '../../extensions/registry'
import { api } from '../../lib/api'
import { colorVars, groupColor } from '../../lib/navTheme'
import { coreNav } from '../../nav'
import { useInboxCount } from '../answers/useInboxCount'
import { type Dashboard, todayLocal } from '../attendance/api'
import { useCan, useMe } from '../auth/useAuth'
import { useLettersCount } from '../letters/useLettersCount'
import { useMeta } from '../meta/useMeta'
import { useNeedCount } from '../needs/useNeedCount'
import type { NotificationPage } from '../notifications/api'
import { NotificationItemRow } from '../notifications/NotificationItemRow'
import { useOpenNotification } from '../notifications/useNotifications'
import { usePendingPenalties } from '../penalties/usePendingCount'
import { useTaskCount } from '../tasks/useTaskCount'

/** Bosh sahifa: salomlashuv, "sizni kutmoqda" topshiriqlari, bugungi davomat, so'nggi xabarlar va barcha bo'limlar (ishga tushirgich). */
export function HomePage() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language === 'ru' ? 'ru' : 'uz'
  const { data: me } = useMe()
  const { data: meta } = useMeta()
  const can = useCan()
  const openNotification = useOpenNotification()

  const tasks = useTaskCount()
  const needs = useNeedCount()
  const inbox = useInboxCount()
  const letters = useLettersCount()
  const penalties = usePendingPenalties()

  const today = todayLocal()
  const day = useQuery({
    queryKey: ['home', 'today', today],
    queryFn: () => api<Dashboard>(`/api/v1/attendance/dashboard?start=${today}&end=${today}`),
    enabled: can('attendance.read'),
    refetchInterval: 120_000,
  })
  const recent = useQuery({ queryKey: ['notifications', 'home'], queryFn: () => api<NotificationPage>('/api/v1/notifications?size=5') })

  const hour = new Date().getHours()
  const greet = hour < 5 ? 'night' : hour < 12 ? 'morning' : hour < 18 ? 'day' : 'evening'
  const first = me?.full_name.split(' ')[1] ?? me?.full_name ?? ''

  const sections = useMemo(() => {
    const items = [...coreNav, ...getExtensionNavItems()].filter((i) => i.id !== 'home' && (!i.module || !meta || meta.modules.includes(i.module)) && (!i.permission || can(i.permission)) && (!i.anyPermission || i.anyPermission.some(can)))
    const map = new Map<string, NavItem[]>()
    for (const it of items) map.set(it.group ?? 'main', [...(map.get(it.group ?? 'main') ?? []), it])
    return [...map.entries()]
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meta, can])

  const waiting: { icon: ComponentType<{ className?: string }>; label: string; n: number; to: string; color: string }[] = [
    { icon: ListTodo, label: t('home.w.tasks'), n: tasks.open, to: '/tasks', color: 'var(--c-indigo)' },
    { icon: AlarmClock, label: t('home.w.overdue'), n: tasks.overdue, to: '/tasks', color: 'var(--c-rose)' },
    { icon: PackagePlus, label: t('home.w.needs'), n: needs, to: '/needs', color: 'var(--c-orange)' },
    { icon: Inbox, label: t('home.w.inbox'), n: inbox, to: '/answers/inbox', color: 'var(--c-amber)' },
    { icon: FileSignature, label: t('home.w.letters'), n: letters, to: '/letters', color: 'var(--c-violet)' },
    { icon: Gavel, label: t('home.w.penalties'), n: penalties, to: '/penalties', color: 'var(--c-slate)' },
  ].filter((w) => w.n > 0)

  const k = day.data?.kpis

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6">
      <section className="rise relative overflow-hidden rounded-[22px] bg-[linear-gradient(120deg,#0b5ed7_0%,#0a3f9c_60%,#3b2b9c_100%)] p-8 text-white shadow-card">
        <div aria-hidden className="absolute -right-10 -top-20 size-80 rounded-full bg-white/10 blur-2xl" />
        <div aria-hidden className="absolute -bottom-24 left-1/3 size-72 rounded-full bg-[#3ecf8e]/20 blur-3xl" />
        <TeamArt className="absolute -right-4 top-1/2 hidden h-80 -translate-y-1/2 md:block" />
        <div className="relative max-w-lg">
          <div className="text-[13px] font-medium text-white/70">{longDate(new Date(), lang)}</div>
          <h1 className="mt-1.5 text-[32px] font-semibold leading-tight tracking-tight">{t(`home.greet.${greet}`, { name: first })}</h1>
          <p className="mt-2 text-[15px] text-white/80">{t('home.subtitle')}</p>
          <div className="mt-5 flex flex-wrap gap-2">
            {can('attendance.punch') && (
              <Link to="/attendance">
                <Button className="bg-white text-[#0a3f9c] hover:bg-white/90 hover:brightness-100">
                  <CalendarCheck2 />
                  {t('home.punch')}
                </Button>
              </Link>
            )}
            <Link to="/profile">
              <Button className="bg-white/15 text-white shadow-none hover:bg-white/25 hover:brightness-100">{t('profile.title')}</Button>
            </Link>
          </div>
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
        <div className="flex flex-col gap-6">
          <Card className="p-5">
            <h2 className="mb-3 flex items-center gap-2 text-[15px] font-semibold">
              <BellRing className="size-4 text-(--c-amber)" />
              {t('home.waiting')}
            </h2>
            {waiting.length === 0 ? (
              <div className="flex items-center gap-3 rounded-xl bg-[color-mix(in_oklab,var(--c-green)_10%,transparent)] px-4 py-3.5 text-sm">
                <CheckCheck className="size-5 text-(--c-green)" />
                {t('home.allClear')}
              </div>
            ) : (
              <div className="grid gap-2.5 sm:grid-cols-2">
                {waiting.map(({ icon: Icon, label, n, to, color }) => (
                  <Link key={label} to={to} style={colorVars(color)} className="group flex items-center gap-3 rounded-xl bg-[color-mix(in_oklab,var(--gc)_9%,transparent)] px-3.5 py-3 transition-colors hover:bg-[color-mix(in_oklab,var(--gc)_16%,transparent)]">
                    <span className="grid size-10 place-items-center rounded-xl bg-(--gc) text-white">
                      <Icon className="size-5" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block font-mono text-xl font-semibold leading-none">{n}</span>
                      <span className="mt-1 block truncate text-xs text-muted">{label}</span>
                    </span>
                    <ArrowRight className="size-4 text-muted transition-transform group-hover:translate-x-0.5" />
                  </Link>
                ))}
              </div>
            )}
          </Card>

          {can('attendance.read') && (
            <Card className="p-5">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="flex items-center gap-2 text-[15px] font-semibold">
                  <CalendarCheck2 className="size-4 text-(--c-teal)" />
                  {t('home.today')}
                </h2>
                <Link to="/attendance/dashboard" className="inline-flex items-center gap-1 text-[13px] text-primary hover:underline">
                  {t('home.details')} <ArrowRight className="size-3.5" />
                </Link>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <Round icon={CalendarCheck2} color="var(--c-green)" value={k?.attended} label={t('home.came')} />
                <Round icon={UserX} color="var(--c-rose)" value={k?.absent} label={t('home.absent')} />
                <Round icon={AlarmClock} color="var(--c-amber)" value={k?.late_count} label={t('home.late')} />
              </div>
            </Card>
          )}
        </div>

        <Card className="flex flex-col p-3">
          <div className="flex items-center justify-between px-2.5 pb-2 pt-2">
            <h2 className="flex items-center gap-2 text-[15px] font-semibold">
              <Inbox className="size-4 text-(--c-blue)" />
              {t('home.recent')}
            </h2>
            <Link to="/notifications" className="text-[13px] text-primary hover:underline">
              {t('home.all')}
            </Link>
          </div>
          {recent.data?.items.length ? (
            recent.data.items.map((n) => <NotificationItemRow key={n.id} n={n} onOpen={openNotification} />)
          ) : (
            <p className="px-3 py-8 text-center text-sm text-muted">{t('home.noRecent')}</p>
          )}
        </Card>
      </div>

      <div className="flex flex-col gap-5">
        <h2 className="text-lg font-semibold tracking-tight">{t('home.modules')}</h2>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {sections.map(([group, items]) => (
            <Card key={group} className="relative overflow-hidden p-4" style={colorVars(groupColor(group as NavItem['group']))}>
              <span aria-hidden className="absolute inset-y-0 left-0 w-1 bg-(--gc)" />
              <div className="mb-2.5 pl-1.5 text-[11px] font-semibold uppercase tracking-wider text-(--gc)">{t(`nav.group.${group}`)}</div>
              <div className="flex flex-col">
                {items.map((l) => {
                  const Icon = l.icon
                  return (
                    <Link key={l.id} to={l.to} className="flex h-10 items-center gap-3 rounded-lg px-1.5 text-sm font-medium transition-colors hover:bg-[color-mix(in_oklab,var(--gc)_10%,transparent)]">
                      {Icon && (
                        <span className="grid size-7 place-items-center rounded-lg bg-[color-mix(in_oklab,var(--gc)_14%,transparent)] text-(--gc)">
                          <Icon className="size-4" />
                        </span>
                      )}
                      <span className="truncate">{l.label[lang]}</span>
                    </Link>
                  )
                })}
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  )
}

const UZ_DAYS = ['yakshanba', 'dushanba', 'seshanba', 'chorshanba', 'payshanba', 'juma', 'shanba']
const UZ_MONTHS = ['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun', 'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr']

function longDate(d: Date, lang: 'uz' | 'ru'): string {
  if (lang === 'ru') return d.toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })
  return `${d.getDate()}-${UZ_MONTHS[d.getMonth()]}, ${UZ_DAYS[d.getDay()]}`
}

function Round({ icon: Icon, color, value, label }: { icon: ComponentType<{ className?: string }>; color: string; value: number | undefined; label: string }) {
  return (
    <div className="flex flex-col items-center gap-1.5 rounded-2xl bg-[color-mix(in_oklab,var(--gc)_9%,transparent)] px-3 py-4 text-center" style={colorVars(color)}>
      <span className="grid size-10 place-items-center rounded-full bg-(--gc) text-white">
        <Icon className="size-5" />
      </span>
      <span className="font-mono text-2xl font-semibold leading-none">{value ?? '—'}</span>
      <span className="text-xs text-muted">{label}</span>
    </div>
  )
}

