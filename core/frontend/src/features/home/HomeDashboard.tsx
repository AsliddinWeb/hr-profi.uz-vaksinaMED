import { useQuery } from '@tanstack/react-query'
import { AlarmClock, ArrowRight, CalendarCheck2, CalendarClock, CheckCircle2, ChevronRight, ClipboardList, Flame, GitBranch, Plane, ShieldAlert, UserX, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { Card } from '../../components/ui/Card'
import { api } from '../../lib/api'
import { colorVars } from '../../lib/navTheme'

type Trend = { date: string; [k: string]: number | string }
export type Overview = {
  date: string
  days: number
  headcount: number | null
  attendance?: { today: { came: number; absent: number; late: number; no_checkout: number; rate: number | null }; trend: Trend[]; top_late: { id: number; name: string; n: number }[] }
  tasks?: { todo: number; in_progress: number; review: number; done: number; overdue: number; done_rate: number | null; done_period: number; trend: Trend[] }
  answers?: { pending: number; approved_month: number; rejected_month: number; on_leave_today: number; upcoming_7d: number; reasons: Record<string, number> }
  problems?: {
    attendance_issues?: number
    letters_open?: number
    letters_month?: number
    penalties_pending?: number
    penalties_month?: number
    tickets_open?: number
    complaints_new?: number
    people_month?: number
    top_people?: { id: number; name: string; n: number }[]
  }
  chain?: { key: string; to: string; value: number; sub: number | null }[]
}

/** Bosh sahifadagi bo'limlar dashboardi: davomat, topshiriqlar, javob/ta'til, muammolar va umumiy ish zanjiri. */
export function HomeDashboard() {
  const { t } = useTranslation()
  const q = useQuery({ queryKey: ['home', 'overview'], queryFn: () => api<Overview>('/api/v1/home/overview'), refetchInterval: 120_000 })
  const d = q.data
  if (!d || (!d.attendance && !d.tasks && !d.answers && !d.problems && !d.chain)) return null
  const p = d.problems

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-end justify-between">
        <h2 className="text-lg font-semibold tracking-tight">{t('home.dash.title')}</h2>
        {d.headcount != null && (
          <span className="text-[13px] text-muted">
            {t('home.dash.headcount')}: <b className="font-mono text-fg">{d.headcount}</b>
          </span>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {d.attendance && (
          <Panel icon={CalendarCheck2} color="var(--c-teal)" title={t('home.dash.attendance')} to="/attendance/dashboard">
            <Stats items={[
              [t('home.came'), d.attendance.today.came, 'var(--c-green)'],
              [t('home.absent'), d.attendance.today.absent, 'var(--c-rose)'],
              [t('home.late'), d.attendance.today.late, 'var(--c-amber)'],
            ]} />
            <Bars data={d.attendance.trend} k="came" color="var(--c-teal)" />
            <Foot>{t('home.dash.rate')}: <b>{d.attendance.today.rate != null ? `${Math.round(d.attendance.today.rate * 100)}%` : '—'}</b></Foot>
          </Panel>
        )}

        {d.tasks && (
          <Panel icon={ClipboardList} color="var(--c-indigo)" title={t('home.dash.tasks')} to="/tasks">
            <Stats items={[
              [t('home.dash.done'), d.tasks.done, 'var(--c-green)'],
              [t('home.dash.inWork'), d.tasks.todo + d.tasks.in_progress + d.tasks.review, 'var(--c-indigo)'],
              [t('home.w.overdue'), d.tasks.overdue, 'var(--c-rose)'],
            ]} />
            <Bars data={d.tasks.trend} k="done" color="var(--c-indigo)" />
            <Foot>
              {t('home.dash.doneWeek', { n: d.tasks.done_period })} · {t('home.dash.doneRate')}: <b>{d.tasks.done_rate ?? '—'}%</b>
            </Foot>
          </Panel>
        )}

        {d.answers && (
          <Panel icon={Plane} color="var(--c-amber)" title={t('home.dash.answers')} to="/answers">
            <Stats items={[
              [t('home.dash.onLeave'), d.answers.on_leave_today, 'var(--c-blue)'],
              [t('home.dash.pending'), d.answers.pending, 'var(--c-amber)'],
              [t('home.dash.upcoming'), d.answers.upcoming_7d, 'var(--c-violet)'],
            ]} />
            <Rows rows={[
              [CheckCircle2, t('home.dash.approvedMonth'), d.answers.approved_month, '/answers'],
              [UserX, t('home.dash.rejectedMonth'), d.answers.rejected_month, '/answers'],
              [CalendarClock, t('home.dash.calendar'), null, '/answers/calendar'],
            ]} />
          </Panel>
        )}

        {p && (
          <Panel icon={ShieldAlert} color="var(--c-rose)" title={t('home.dash.problems')} to="/letters">
            <Stats items={[
              [t('home.dash.problemPeople'), p.people_month ?? 0, 'var(--c-rose)'],
              [t('home.dash.lettersOpen'), p.letters_open ?? 0, 'var(--c-violet)'],
              [t('home.dash.penaltiesPending'), p.penalties_pending ?? 0, 'var(--c-slate)'],
            ]} />
            <Rows rows={[
              ...(p.attendance_issues != null ? [[AlarmClock, t('home.dash.issues'), p.attendance_issues, '/attendance/issues'] as Row] : []),
              ...(p.tickets_open != null ? [[Flame, t('home.dash.tickets'), p.tickets_open, '/helpdesk'] as Row] : []),
              ...(p.complaints_new != null ? [[ShieldAlert, t('home.dash.complaints'), p.complaints_new, '/complaints'] as Row] : []),
            ]} />
            {!!p.top_people?.length && (
              <div className="mt-2 border-t border-border pt-2">
                <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-muted">{t('home.dash.topPeople')}</div>
                {p.top_people.map((x) => (
                  <Link key={x.id} to={`/employees/${x.id}`} className="flex items-center justify-between rounded px-1 py-0.5 text-[13px] hover:bg-surface-2">
                    <span className="truncate">{x.name}</span>
                    <span className="font-mono text-(--c-rose)">{x.n}</span>
                  </Link>
                ))}
              </div>
            )}
          </Panel>
        )}
      </div>

      {!!d.chain?.length && (
        <Card className="p-5">
          <h3 className="mb-3 flex items-center gap-2 text-[15px] font-semibold">
            <GitBranch className="size-4 text-(--c-blue)" />
            {t('home.dash.chain')}
          </h3>
          <div className="flex flex-wrap items-stretch gap-1.5">
            {d.chain.map((s, i) => (
              <div key={s.key} className="flex items-center gap-1.5">
                {i > 0 && <ChevronRight className="size-4 shrink-0 text-muted" />}
                <Link to={s.to} className="min-w-28 rounded-xl border border-border px-3 py-2 transition-colors hover:border-primary hover:bg-surface-2">
                  <div className="font-mono text-xl font-semibold leading-none">{s.value}</div>
                  <div className="mt-1 text-xs text-muted">{t(`home.dash.step.${s.key}`)}</div>
                  {s.sub != null && <div className="mt-0.5 text-[11px] text-muted">{t(`home.dash.stepSub.${s.key}`, { n: s.sub })}</div>}
                </Link>
              </div>
            ))}
          </div>
        </Card>
      )}
    </section>
  )
}

type Row = [LucideIcon, string, number | null, string]

function Panel({ icon: Icon, color, title, to, children }: { icon: LucideIcon; color: string; title: string; to: string; children: ReactNode }) {
  const { t } = useTranslation()
  return (
    <Card className="relative flex flex-col gap-3 overflow-hidden p-4" style={colorVars(color)}>
      <span aria-hidden className="absolute inset-x-0 top-0 h-1 bg-(--gc)" />
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-[14px] font-semibold">
          <span className="grid size-7 place-items-center rounded-lg bg-[color-mix(in_oklab,var(--gc)_14%,transparent)] text-(--gc)">
            <Icon className="size-4" />
          </span>
          {title}
        </h3>
        <Link to={to} className="inline-flex items-center gap-0.5 text-[12px] text-primary hover:underline">
          {t('home.details')} <ArrowRight className="size-3" />
        </Link>
      </div>
      {children}
    </Card>
  )
}

function Stats({ items }: { items: [string, number, string][] }) {
  return (
    <div className="grid grid-cols-3 gap-2">
      {items.map(([label, n, color]) => (
        <div key={label} style={colorVars(color)} className="rounded-lg bg-[color-mix(in_oklab,var(--gc)_9%,transparent)] px-2 py-2 text-center">
          <div className="font-mono text-lg font-semibold leading-none text-(--gc)">{n}</div>
          <div className="mt-1 truncate text-[11px] text-muted" title={label}>
            {label}
          </div>
        </div>
      ))}
    </div>
  )
}

function Bars({ data, k, color }: { data: Trend[]; k: string; color: string }) {
  const max = Math.max(1, ...data.map((x) => Number(x[k]) || 0))
  return (
    <div className="flex h-14 items-end gap-1" style={colorVars(color)}>
      {data.map((x) => {
        const v = Number(x[k]) || 0
        return (
          <div key={x.date} className="flex flex-1 flex-col items-center gap-0.5" title={`${x.date}: ${v}`}>
            <div className="w-full rounded-t bg-(--gc) opacity-80" style={{ height: `${Math.max(4, (v / max) * 44)}px` }} />
            <span className="text-[9px] text-muted">{x.date.slice(8, 10)}</span>
          </div>
        )
      })}
    </div>
  )
}

function Rows({ rows }: { rows: Row[] }) {
  return (
    <div className="flex flex-col">
      {rows.map(([Icon, label, n, to]) => (
        <Link key={label} to={to} className="flex items-center gap-2 rounded px-1 py-1 text-[13px] hover:bg-surface-2">
          <Icon className="size-3.5 text-muted" />
          <span className="flex-1 truncate">{label}</span>
          {n != null ? <span className="font-mono font-semibold">{n}</span> : <ArrowRight className="size-3 text-muted" />}
        </Link>
      ))}
    </div>
  )
}

function Foot({ children }: { children: ReactNode }) {
  return <div className="text-[12px] text-muted">{children}</div>
}
