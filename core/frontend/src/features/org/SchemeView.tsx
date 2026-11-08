import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { Avatar } from '../employees/Avatar'

interface P {
  id: number | null
  full_name: string
  photo: boolean
}
interface Pos {
  id: number
  name: string
  yqm: string | null
  occupants: P[]
}
interface Dept {
  id: number
  name: string
  yqm: string | null
  color: string | null
  head: P | null
  positions: Pos[]
  children: Dept[]
  headcount: number
}
interface Scheme {
  company: string
  leadership: (P & { role: string; role_ru: string })[]
  departments: Dept[]
  general: Pos[]
}

const vacancyCls = 'inline-block rounded-md bg-orange-500 px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wide text-white shadow-sm'
const pillCls = 'rounded-xl border border-sky-200 bg-white px-3 py-1.5 text-center text-[12px] font-semibold italic text-[#1f3a68] shadow-sm dark:border-sky-900 dark:bg-[#141b2b] dark:text-sky-200'

function Person({ p }: { p: P }) {
  const body = (
    <span className="inline-flex max-w-full items-center gap-2 rounded-full border border-border bg-surface py-0.5 pl-0.5 pr-3 text-[12px] font-medium shadow-sm">
      {p.id ? <Avatar id={p.id} name={p.full_name} hasPhoto={p.photo} size={24} className="rounded-full" /> : <span className="size-6 rounded-full bg-surface-3" />}
      <span className="truncate">{p.full_name}</span>
    </span>
  )
  return p.id ? <Link to={`/employees/${p.id}`} className="max-w-full hover:opacity-80">{body}</Link> : body
}

function Occupants({ list }: { list: P[] }) {
  const { t } = useTranslation()
  if (!list.length) return <span className={vacancyCls}>{t('scheme.vacancy')}</span>
  return (
    <div className="flex flex-col items-center gap-1">
      {list.map((p, i) => (
        <Person key={p.id ?? `${p.full_name}-${i}`} p={p} />
      ))}
    </div>
  )
}

function Yqm({ text }: { text: string | null }) {
  const { t } = useTranslation()
  if (!text) return null
  return (
    <p className="text-[11px] leading-snug text-muted">
      <b className="text-text">{t('scheme.yqm')}:</b> {text}
    </p>
  )
}

/** Bitta bo'lim ustuni: nom + YaQM → boshliq → raqamlangan lavozimlar (egasi yoki VAKANSIYA) → ichki bo'limlar. */
function Column({ d, nested = false }: { d: Dept; nested?: boolean }) {
  const { t } = useTranslation()
  return (
    <div className={nested ? 'mt-3 border-l-2 border-sky-200 pl-3 dark:border-sky-900' : 'w-64 shrink-0'}>
      <div className="flex flex-col items-center gap-2 text-center">
        <div className="relative pt-3">
          {!nested && <span aria-hidden className="absolute left-1/2 top-0 h-3 w-px bg-sky-300" />}
          <h3 className="text-[13px] font-bold uppercase tracking-wide" style={d.color ? { color: d.color } : undefined}>
            {d.name}
          </h3>
          <Yqm text={d.yqm} />
        </div>
        <div className={pillCls}>{t('scheme.head')}</div>
        {d.head ? <Person p={d.head} /> : <span className={vacancyCls}>{t('scheme.vacancy')}</span>}
        {d.positions.map((p, i) => (
          <div key={p.id} className="flex w-full flex-col items-center gap-1.5">
            <span aria-hidden className="h-3 w-px bg-sky-300" />
            <div className={`${pillCls} w-full`}>
              {i + 1}. {p.name}
            </div>
            <Occupants list={p.occupants} />
            <Yqm text={p.yqm} />
          </div>
        ))}
        {d.positions.length === 0 && <p className="text-[11px] text-muted">{t('scheme.noPositions')}</p>}
      </div>
      {d.children.map((c) => (
        <Column key={c.id} d={c} nested />
      ))}
    </div>
  )
}

/** Tashkiliy tuzilma sxemasi (shablon ko'rinishi). Bo'lim/lavozim/xodim qo'shilganda avtomatik yangilanadi. */
export function SchemeView() {
  const { t, i18n } = useTranslation()
  const q = useQuery({ queryKey: ['org', 'scheme'], queryFn: () => api<Scheme>('/api/v1/org/scheme') })
  const d = q.data
  if (!d) return <Skeleton className="h-96" />
  const ru = i18n.language === 'ru'
  return (
    <div className="overflow-x-auto rounded-card bg-gradient-to-b from-sky-50/70 to-transparent p-6 dark:from-sky-950/20">
      <div className="mx-auto flex min-w-max flex-col items-center">
        <div className="rounded-2xl border border-sky-200 bg-white px-8 py-3 text-center shadow-card dark:border-sky-900 dark:bg-[#141b2b]">
          <div className="text-xl font-extrabold tracking-wide text-[#1f3a68] dark:text-sky-200">{d.company}</div>
          <div className="text-xs text-muted">{t('scheme.company')}</div>
        </div>
        <span aria-hidden className="h-4 w-px bg-sky-300" />
        {d.leadership.length > 0 && (
          <div className="flex flex-wrap justify-center gap-6">
            {d.leadership.map((l, i) => (
              <div key={`${l.id}-${i}`} className="flex flex-col items-center gap-1.5">
                <div className={pillCls}>{ru ? l.role_ru : l.role}</div>
                <Person p={l} />
              </div>
            ))}
          </div>
        )}
        <span aria-hidden className="h-4 w-px bg-sky-300" />
        <div className="relative flex items-start gap-5 border-t border-sky-300 pt-0">
          {/* Birinchi daraja: ildiz bo'lim (masalan Rahbariyat) va uning ichki bo'limlari yonma-yon ustunlar (shablon kabi) */}
          {d.departments.flatMap((dep) => [{ ...dep, children: [] }, ...dep.children]).map((dep) => (
            <Column key={dep.id} d={dep} />
          ))}
          {d.general.length > 0 && (
            <div className="w-64 shrink-0">
              <div className="flex flex-col items-center gap-2 pt-3 text-center">
                <h3 className="text-[13px] font-bold uppercase tracking-wide text-muted">{t('scheme.general')}</h3>
                {d.general.map((p, i) => (
                  <div key={p.id} className="flex w-full flex-col items-center gap-1.5">
                    <div className={`${pillCls} w-full`}>
                      {i + 1}. {p.name}
                    </div>
                    <Occupants list={p.occupants} />
                    <Yqm text={p.yqm} />
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
