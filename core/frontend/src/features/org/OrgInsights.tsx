import { Store, Briefcase, Clock, TrendingDown, UserMinus, UserPlus, Users } from 'lucide-react'
import { useState, type ComponentType } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { cn } from '../../lib/cn'
import { formatDate } from '../../lib/format'
import { Avatar } from '../employees/Avatar'
import { tenureText, type Insights, type Person } from './orgInsightsApi'

/** Yuqori ko'rsatkichlar qatori. */
export function InsightKpis({ d }: { d: Insights }) {
  const { t } = useTranslation()
  const a = d.analytics
  const items: [ComponentType<{ className?: string }>, string, string, string][] = [
    [Users, t('orgx.headcount'), String(d.headcount), 'text-primary'],
    [Briefcase, t('orgx.positions'), `${d.positions_total}`, 'text-violet-600'],
    [Store, t('orgx.branches'), String(d.branches_total ?? 0), 'text-orange-600'],
    [UserPlus, t('orgx.hired12'), String(a.hired_12m), 'text-emerald-600'],
    [UserMinus, t('orgx.left12'), String(a.left_12m), 'text-rose-600'],
    [TrendingDown, t('orgx.turnover'), `${a.turnover_pct}%`, 'text-amber-600'],
    [Clock, t('orgx.avgTenure'), tenureText(t, a.avg_tenure_months === null ? null : Math.round(a.avg_tenure_months)), 'text-sky-600'],
  ]
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {items.map(([Icon, label, value, tone]) => (
        <Card key={label} className="flex flex-col gap-1 p-4">
          <Icon className={`size-5 ${tone}`} />
          <span className="text-xl font-bold tabular-nums">{value}</span>
          <span className="text-xs text-muted">{label}</span>
        </Card>
      ))}
    </div>
  )
}

/** Oyma-oy kelish/ketish grafigi va staj/filial taqsimoti. */
export function InsightCharts({ d }: { d: Insights }) {
  const { t } = useTranslation()
  const a = d.analytics
  const max = Math.max(1, ...a.months.map((m) => Math.max(m.hired, m.left)))
  const tb = a.tenure_buckets
  const tbTotal = Math.max(1, tb.lt3 + tb.m3_12 + tb.y1_3 + tb.gt3y)
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Card className="flex flex-col gap-3 p-5 lg:col-span-2">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">{t('orgx.flow12')}</h3>
          <span className="flex gap-3 text-[11px] text-muted">
            <span className="flex items-center gap-1"><i className="size-2 rounded-full bg-emerald-500" />{t('orgx.hired')}</span>
            <span className="flex items-center gap-1"><i className="size-2 rounded-full bg-rose-500" />{t('orgx.left')}</span>
          </span>
        </div>
        <div className="flex h-36 items-end gap-1.5">
          {a.months.map((m) => (
            <div key={m.month} className="flex h-full flex-1 flex-col items-center justify-end gap-1" title={`${m.month}: +${m.hired} / −${m.left}`}>
              <div className="flex h-full w-full items-end justify-center gap-0.5">
                <div className="w-1/2 rounded-t-sm bg-emerald-500" style={{ height: `${(m.hired / max) * 100}%` }} />
                <div className="w-1/2 rounded-t-sm bg-rose-500" style={{ height: `${(m.left / max) * 100}%` }} />
              </div>
              <span className="text-[10px] text-muted">{m.month.slice(5)}</span>
            </div>
          ))}
        </div>
      </Card>
      <Card className="flex flex-col gap-3 p-5">
        <h3 className="text-sm font-semibold">{t('orgx.tenureDist')}</h3>
        {(['lt3', 'm3_12', 'y1_3', 'gt3y'] as const).map((k) => (
          <div key={k}>
            <div className="flex justify-between text-xs">
              <span>{t(`orgx.tb.${k}`)}</span>
              <span className="font-semibold tabular-nums">{tb[k]}</span>
            </div>
            <div className="mt-1 h-1.5 rounded-full bg-surface-2">
              <div className="h-full rounded-full bg-primary" style={{ width: `${(tb[k] / tbTotal) * 100}%` }} />
            </div>
          </div>
        ))}
        <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted">
          {a.avg_age !== null && <Badge>{t('orgx.avgAge', { n: a.avg_age })}</Badge>}
          {Object.entries(a.gender).map(([g, n]) => (
            <Badge key={g}>{t(`orgx.g.${g}`, { defaultValue: g })}: {n}</Badge>
          ))}
        </div>
      </Card>
    </div>
  )
}

function PersonCard({ p, mode }: { p: Person; mode: 'staff' | 'new' | 'left' }) {
  const { t, i18n } = useTranslation()
  return (
    <Link to={`/employees/${p.id}`} className="flex items-center gap-3 rounded-control border border-border bg-surface p-2.5 transition hover:border-primary/50 hover:bg-surface-2">
      <Avatar id={p.id} name={p.full_name} hasPhoto={p.photo} size={40} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium">{p.full_name}</span>
        <span className="block truncate text-xs text-muted">
          {mode === 'staff' ? [p.branch, tenureText(t, p.tenure_months)].filter(Boolean).join(' · ') : [p.position, p.branch].filter(Boolean).join(' · ')}
        </span>
        {mode === 'new' && p.hire_date && <span className="block text-[11px] text-emerald-600">{t('orgx.joined', { d: formatDate(p.hire_date, i18n.language) })}</span>}
        {mode === 'left' && p.dismissal_date && (
          <span className="block text-[11px] text-rose-600">
            {t('orgx.leftOn', { d: formatDate(p.dismissal_date, i18n.language) })} · {tenureText(t, p.tenure_months)}
          </span>
        )}
      </span>
    </Link>
  )
}

type Tab = 'positions' | 'new' | 'left' | 'analytics'

/** Bo'lim (yoki kompaniya) bo'yicha: lavozimlar → xodimlar, yangi kelganlar, ishdan ketganlar arxivi va tahlil. */
export function InsightTabs({ d, defaultTab = 'positions' }: { d: Insights; defaultTab?: Tab }) {
  const { t } = useTranslation()
  const [tab, setTab] = useState<Tab>(defaultTab)
  const tabs: [Tab, string, number | null][] = [
    ['positions', t('orgx.tab.positions'), d.headcount],
    ['new', t('orgx.tab.new'), d.newcomers_count],
    ['left', t('orgx.tab.left'), d.leavers_count],
    ['analytics', t('orgx.tab.analytics'), null],
  ]
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-2">
        {tabs.map(([k, label, n]) => (
          <button key={k} type="button" onClick={() => setTab(k)} className={cn('rounded-full px-3.5 py-1.5 text-xs font-semibold', tab === k ? 'bg-primary text-primary-fg' : 'border border-border bg-surface hover:bg-surface-2')}>
            {label}
            {n !== null && <span className="ml-1.5 opacity-70">{n}</span>}
          </button>
        ))}
      </div>
      {!d.can_see_people && tab !== 'analytics' && <p className="text-sm text-muted">{t('orgx.noPeopleAccess')}</p>}
      {tab === 'positions' && d.can_see_people && (
        <div className="flex flex-col gap-3">
          {[...d.positions].sort((a, b) => b.count - a.count).map((p) => (
            <Card key={p.id} className="p-4">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <Briefcase className="size-4 text-primary" />
                <h4 className="font-semibold">{p.name}</h4>
                {p.general && <Badge>{t('orgx.general')}</Badge>}
                {p.department && d.scope.department_id === null && <span className="text-xs text-muted">{p.department}</span>}
                <Badge tone={p.count ? 'info' : 'warning'} className="ml-auto">{p.count ? t('orgx.people', { n: p.count }) : t('orgx.vacant')}</Badge>
              </div>
              {p.count > 0 && (
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {p.employees.map((e) => <PersonCard key={e.id} p={e} mode="staff" />)}
                </div>
              )}
            </Card>
          ))}
          {d.no_position_count > 0 && (
            <Card className="p-4">
              <h4 className="mb-2 font-semibold text-warning">{t('orgx.noPosition', { n: d.no_position_count })}</h4>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {d.no_position.map((e) => <PersonCard key={e.id} p={e} mode="staff" />)}
              </div>
            </Card>
          )}
          {d.positions.length === 0 && <p className="text-sm text-muted">{t('orgx.noPositions')}</p>}
        </div>
      )}
      {tab === 'new' && d.can_see_people && (
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {d.newcomers.map((e) => <PersonCard key={e.id} p={e} mode="new" />)}
          {d.newcomers.length === 0 && <p className="text-sm text-muted">{t('orgx.noNew')}</p>}
        </div>
      )}
      {tab === 'left' && d.can_see_people && (
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {d.leavers.map((e) => <PersonCard key={e.id} p={e} mode="left" />)}
          {d.leavers.length === 0 && <p className="text-sm text-muted">{t('orgx.noLeft')}</p>}
        </div>
      )}
      {tab === 'analytics' && (
        <div className="flex flex-col gap-4">
          <InsightCharts d={d} />
          {d.analytics.by_branch.length > 0 && (
            <Card className="flex flex-col gap-2 p-5">
              <h3 className="text-sm font-semibold">{t('orgx.byBranch')}</h3>
              {d.analytics.by_branch.map((b) => (
                <div key={b.name} className="flex items-center gap-3 text-sm">
                  <span className="w-48 truncate">{b.name}</span>
                  <div className="h-2 flex-1 rounded-full bg-surface-2">
                    <div className="h-full rounded-full bg-primary" style={{ width: `${(b.count / Math.max(1, d.analytics.by_branch[0].count)) * 100}%` }} />
                  </div>
                  <span className="w-8 text-right font-semibold tabular-nums">{b.count}</span>
                </div>
              ))}
            </Card>
          )}
        </div>
      )}
    </div>
  )
}

export function InsightsLoading() {
  return <Skeleton className="h-48" />
}
