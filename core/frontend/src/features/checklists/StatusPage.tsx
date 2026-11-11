import { useQuery } from '@tanstack/react-query'
import { CalendarDays, ClipboardCheck, MapPin, Star, Target, TrendingUp, Users } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'

import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Select } from '../../components/ui/Input'
import { Tabs } from '../../components/ui/Tabs'
import { api } from '../../lib/api'

type Status = {
  kpis: { visits: number; branches: number; coordinators: number; avg_score: number | null; coverage: { visited: number; total: number }; gps_pct: number | null }
  score_buckets: { good: number; mid: number; low: number }
  answers: { yes: number; no: number }
  process: { gps: number; no_gps: number; not_visited: number }
  daily: { date: string; n: number }[]
  coordinators: { id: number; name: string }[]
}
type RankRow = { id: number; name: string; points: number; level: string; visits: number; branches: number; avg_score: number; gps_pct: number; last: string | null }
type TabKey = 'dashboard' | 'time' | 'ranking' | 'visits' | 'coverage'
const LEVEL: Record<string, string> = { good: 'var(--c-green)', mid: 'var(--c-amber)', low: 'var(--c-rose)', none: 'var(--c-slate)' }
const d8 = (s: string | null) => (s ? new Date(s).toLocaleDateString('ru-RU') : '—')

/** /checklists/status — Cheklist holati: koordinatorlar filialga qachon kelgani, cheklistni qanday to'ldirgani va qancha vaqt qolgani. */
export function ChecklistStatusPage() {
  const { t } = useTranslation()
  const [sp, setSp] = useSearchParams()
  const tab = (sp.get('tab') as TabKey) || 'dashboard'
  const [period, setPeriod] = useState('all')
  const [coord, setCoord] = useState(0)
  const qs = new URLSearchParams({ period, ...(coord ? { coordinator_id: String(coord) } : {}) }).toString()
  const st = useQuery({ queryKey: ['checklists', 'status', qs], queryFn: () => api<Status>(`/api/v1/checklists/status?${qs}`) })
  const limit = useQuery({ queryKey: ['company-settings'], queryFn: () => api<{ values: Record<string, number> }>('/api/v1/company-settings') })
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <section className="rounded-[22px] bg-[linear-gradient(120deg,#0f2a4a_0%,#16325c_100%)] p-6 text-white shadow-card">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-white/60">{t('cls.kicker')}</div>
        <h1 className="mt-1 text-2xl font-semibold">{t('cls.title')}</h1>
        <p className="mt-1 max-w-2xl text-sm text-white/75">{t('cls.subtitle')}</p>
        <span className="mt-3 inline-block rounded-full bg-white/10 px-3 py-1 text-xs">{t('cls.rule', { n: limit.data?.values['checklists.month_limit'] ?? 4 })}</span>
      </section>
      <Tabs<TabKey>
        value={tab}
        onChange={(k) => setSp({ tab: k })}
        items={(['dashboard', 'time', 'ranking', 'visits', 'coverage'] as const).map((k) => ({ key: k, label: t(`cls.tab.${k}`) }))}
      />
      {tab !== 'ranking' && tab !== 'coverage' && tab !== 'visits' && (
        <div className="flex flex-wrap items-center gap-2">
          <Select value={coord} onChange={(e) => setCoord(Number(e.target.value))} aria-label={t('cls.coordinator')}>
            <option value={0}>{t('cls.allCoordinators')}</option>
            {st.data?.coordinators.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </Select>
          <div className="ml-auto flex gap-1">
            {['all', 'today', '7d', '30d'].map((p) => <Button key={p} variant={period === p ? 'primary' : 'ghost'} onClick={() => setPeriod(p)}>{t(`cls.p.${p}`)}</Button>)}
          </div>
        </div>
      )}
      {tab === 'dashboard' && st.data && <Dashboard s={st.data} />}
      {tab === 'time' && <TimeTab period={period} coord={coord} />}
      {tab === 'ranking' && <Ranking full />}
      {tab === 'visits' && (
        <Card className="flex items-center justify-between p-5">
          <span>{t('cls.visitsHint')}</span>
          <Link to="/checklists"><Button><ClipboardCheck className="size-4" />{t('cls.openVisits')}</Button></Link>
        </Card>
      )}
      {tab === 'coverage' && <Coverage coordinators={st.data?.coordinators ?? []} />}
    </div>
  )
}

function Kpi({ icon: Icon, label, value, sub }: { icon: typeof Users; label: string; value: string | number; sub?: string }) {
  return (
    <Card className="p-3">
      <Icon className="size-4 text-primary" />
      <div className="mt-2 text-[10px] font-semibold uppercase tracking-wider text-muted">{label}</div>
      <div className="font-mono text-2xl font-semibold">{value}</div>
      {sub && <div className="text-[11px] text-muted">{sub}</div>}
    </Card>
  )
}

function Bar({ parts }: { parts: [string, number, string][] }) {
  const total = Math.max(1, parts.reduce((a, [, n]) => a + n, 0))
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex h-2 overflow-hidden rounded-full bg-surface-2">{parts.map(([l, n, c]) => <div key={l} style={{ width: `${(n / total) * 100}%`, background: c }} />)}</div>
      {parts.map(([l, n, c]) => <div key={l} className="flex justify-between text-[13px]"><span className="flex items-center gap-1.5"><i className="size-2 rounded-full" style={{ background: c }} />{l}</span><b>{n}</b></div>)}
    </div>
  )
}

function Dashboard({ s }: { s: Status }) {
  const { t } = useTranslation()
  const k = s.kpis
  const max = Math.max(1, ...s.daily.map((d) => d.n))
  const cov = k.coverage.total ? Math.round((k.coverage.visited / k.coverage.total) * 100) : 0
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Kpi icon={ClipboardCheck} label={t('cls.k.visits')} value={k.visits} />
        <Kpi icon={MapPin} label={t('cls.k.branches')} value={k.branches} />
        <Kpi icon={Users} label={t('cls.k.coordinators')} value={k.coordinators} />
        <Kpi icon={TrendingUp} label={t('cls.k.avg')} value={k.avg_score != null ? `${Math.round(k.avg_score)}%` : '—'} />
        <Kpi icon={Target} label={t('cls.k.coverage')} value={`${cov}%`} sub={`${k.coverage.visited}/${k.coverage.total}`} />
        <Kpi icon={MapPin} label="GPS" value={k.gps_pct != null ? `${k.gps_pct}%` : '—'} sub={t('cls.k.ofVisits', { n: k.visits })} />
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <Card className="p-4"><div className="mb-3 font-semibold">{t('cls.scoreState')}</div><Bar parts={[[t('cls.b.good'), s.score_buckets.good, 'var(--c-green)'], [t('cls.b.mid'), s.score_buckets.mid, 'var(--c-amber)'], [t('cls.b.low'), s.score_buckets.low, 'var(--c-rose)']]} /></Card>
        <Card className="p-4"><div className="mb-3 font-semibold">{t('cls.answers')}</div><Bar parts={[[t('cls.yes'), s.answers.yes, 'var(--c-green)'], [t('cls.no'), s.answers.no, 'var(--c-rose)']]} /></Card>
        <Card className="p-4"><div className="mb-3 font-semibold">{t('cls.process')}</div><Bar parts={[[t('cls.gps'), s.process.gps, 'var(--c-blue)'], [t('cls.noGps'), s.process.no_gps, 'var(--c-slate)'], [t('cls.notVisited'), s.process.not_visited, 'var(--c-rose)']]} /></Card>
      </div>
      <div className="grid gap-4 md:grid-cols-[2fr_1fr]">
        <Card className="p-4">
          <div className="font-semibold">{t('cls.daily')}</div>
          <div className="text-xs text-muted">{t('cls.dailyHint')}</div>
          <div className="mt-3 flex h-36 items-end gap-1">
            {s.daily.map((d) => (
              <div key={d.date} className="flex flex-1 flex-col items-center gap-1" title={`${d.date}: ${d.n}`}>
                <div className="w-full rounded-t bg-(--c-blue)" style={{ height: `${Math.max(2, (d.n / max) * 110)}px` }} />
                <span className="text-[9px] text-muted">{d.date.slice(8, 10)}.{d.date.slice(5, 7)}</span>
              </div>
            ))}
          </div>
        </Card>
        <Card className="p-4">
          <div className="font-semibold">{t('cls.distribution')}</div>
          <div className="mb-3 text-xs text-muted">{t('cls.distributionHint')}</div>
          <Bar parts={[[t('cls.b.goodShort'), s.score_buckets.good, 'var(--c-green)'], [t('cls.b.midShort'), s.score_buckets.mid, 'var(--c-amber)'], [t('cls.b.lowShort'), s.score_buckets.low, 'var(--c-rose)']]} />
        </Card>
      </div>
      <Ranking />
    </div>
  )
}

function Ranking({ full = false }: { full?: boolean }) {
  const { t } = useTranslation()
  const [span, setSpan] = useState('week')
  const r = useQuery({ queryKey: ['checklists', 'status', 'ranking', span], queryFn: () => api<{ start: string; end: string; items: RankRow[] }>(`/api/v1/checklists/status/ranking?span=${span}`) })
  const items = full ? r.data?.items : r.data?.items.slice(0, 12)
  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2 font-semibold"><Star className="size-4 text-(--c-amber)" />{t('cls.ranking')}</div>
          <div className="text-xs text-muted">{t('cls.rankingHint')} {r.data && `${t('cls.span')}: ${d8(r.data.start)} — ${d8(r.data.end)}`}</div>
        </div>
        <div className="flex gap-1">{['day', 'week', 'month'].map((s) => <Button key={s} variant={span === s ? 'primary' : 'ghost'} onClick={() => setSpan(s)}>{t(`cls.s.${s}`)}</Button>)}</div>
      </div>
      <div className="mt-3 flex flex-col divide-y divide-border">
        {items?.map((x, i) => (
          <div key={x.id} className="flex items-center gap-3 py-2">
            <span className="w-6 text-center font-mono text-muted">{i + 1}</span>
            <div className="min-w-0 flex-1">
              <div className="font-medium">{x.name}</div>
              <div className="text-xs text-muted">{t('cls.rankLine', { v: x.visits, b: x.branches, s: Math.round(x.avg_score) })}{x.last && ` · ${t('cls.last')}: ${d8(x.last)}`}</div>
            </div>
            <span className="font-mono font-semibold">{x.points}/100</span>
            <span className="rounded-full px-2 py-0.5 text-[11px] font-semibold text-white" style={{ background: LEVEL[x.level] }}>{t(`cls.lv.${x.level}`)}</span>
          </div>
        ))}
      </div>
    </Card>
  )
}

function TimeTab({ period, coord }: { period: string; coord: number }) {
  const { t } = useTranslation()
  const d = useQuery({
    queryKey: ['checklists', 'status', 'time', period, coord],
    queryFn: () => api<{ avg_minutes: number | null; short: number; long: number; hours: { hour: number; n: number }[]; by_coordinator: { id: number; name: string; visits: number; avg_minutes: number }[]; recent: { id: number; branch: string; coordinator: string; started_at: string; minutes: number }[] }>(`/api/v1/checklists/status/time?period=${period}${coord ? `&coordinator_id=${coord}` : ''}`),
  })
  const x = d.data
  const max = Math.max(1, ...(x?.hours.map((h) => h.n) ?? [1]))
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-3 gap-3">
        <Kpi icon={CalendarDays} label={t('cls.t.avg')} value={x?.avg_minutes != null ? `${x.avg_minutes} ${t('cls.min')}` : '—'} />
        <Kpi icon={CalendarDays} label={t('cls.t.short')} value={x?.short ?? 0} />
        <Kpi icon={CalendarDays} label={t('cls.t.long')} value={x?.long ?? 0} />
      </div>
      <Card className="p-4">
        <div className="mb-3 font-semibold">{t('cls.t.hours')}</div>
        <div className="flex h-28 items-end gap-1">
          {x?.hours.map((h) => <div key={h.hour} className="flex flex-1 flex-col items-center gap-1"><div className="w-full rounded-t bg-(--c-teal)" style={{ height: `${Math.max(2, (h.n / max) * 90)}px` }} /><span className="text-[9px] text-muted">{h.hour}</span></div>)}
        </div>
      </Card>
      <div className="grid gap-4 md:grid-cols-2">
        <Card className="p-4">
          <div className="mb-2 font-semibold">{t('cls.t.byCoord')}</div>
          {x?.by_coordinator.map((c) => <div key={c.id} className="flex justify-between py-1 text-sm"><span>{c.name}</span><span className="font-mono">{c.avg_minutes} {t('cls.min')} · {c.visits}</span></div>)}
        </Card>
        <Card className="p-4">
          <div className="mb-2 font-semibold">{t('cls.t.recent')}</div>
          {x?.recent.map((r) => <div key={r.id} className="flex justify-between py-1 text-sm"><span className="truncate">{r.branch} · {r.coordinator}</span><span className="font-mono">{new Date(r.started_at).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })} · {r.minutes} {t('cls.min')}</span></div>)}
        </Card>
      </div>
    </div>
  )
}

function Coverage({ coordinators }: { coordinators: { id: number; name: string }[] }) {
  const { t } = useTranslation()
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7))
  const [coord, setCoord] = useState(0)
  const d = useQuery({
    queryKey: ['checklists', 'status', 'coverage', month, coord],
    queryFn: () => api<{ limit: number; visited: number; total: number; over_limit: number; items: { id: number; name: string; coordinator: string | null; visits: number; limit: number; over_limit: boolean; avg_score: number | null; last: string | null }[] }>(`/api/v1/checklists/status/coverage?month=${month}${coord ? `&coordinator_id=${coord}` : ''}`),
  })
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-2">
        <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="h-10 rounded-control border border-border bg-surface px-3" />
        <Select value={coord} onChange={(e) => setCoord(Number(e.target.value))}>
          <option value={0}>{t('cls.allCoordinators')}</option>
          {coordinators.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </Select>
        {d.data && <span className="ml-auto self-center text-sm text-muted">{t('cls.covSummary', { v: d.data.visited, t: d.data.total, o: d.data.over_limit })}</span>}
      </div>
      <Card className="divide-y divide-border">
        {d.data?.items.map((b) => (
          <div key={b.id} className="flex flex-wrap items-center gap-3 p-3">
            <div className="min-w-48 flex-1"><div className="font-medium">{b.name}</div><div className="text-xs text-muted">{b.coordinator ?? '—'} · {t('cls.last')}: {d8(b.last)}</div></div>
            <div className="flex gap-1">{Array.from({ length: b.limit }, (_, i) => <i key={i} className={`size-3 rounded-full ${i < b.visits ? 'bg-(--c-green)' : 'bg-surface-2'}`} />)}</div>
            <span className={`w-14 text-right font-mono ${b.over_limit ? 'text-danger' : b.visits ? '' : 'text-muted'}`}>{b.visits}/{b.limit}</span>
            <span className="w-14 text-right font-mono text-sm">{b.avg_score != null ? `${Math.round(b.avg_score)}%` : '—'}</span>
          </div>
        ))}
      </Card>
    </div>
  )
}
