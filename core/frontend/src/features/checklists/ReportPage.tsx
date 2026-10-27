import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { addDays, todayLocal } from '../attendance/api'
import { scoreText, scoreTone, type CoverageRow, type Ranking, type TrendPoint } from './api'

/** /checklists/report: filial qamrovi, reyting va haftalik trend. */
export function ReportPage() {
  const { t, i18n } = useTranslation()
  const today = todayLocal()
  const [range, setRange] = useState({ start: addDays(today, -89), end: today })
  const [days, setDays] = useState(14)
  const [branch, setBranch] = useState('')
  const valid = range.end >= range.start && (new Date(range.end).getTime() - new Date(range.start).getTime()) / 86400000 <= 400
  const qs = new URLSearchParams({ start: range.start, end: range.end })
  const cov = useQuery({ queryKey: ['checklists', 'coverage', qs.toString(), days], queryFn: () => api<{ items: CoverageRow[] }>(`/api/v1/checklists/coverage?${qs}&days=${days}`), enabled: valid })
  const rank = useQuery({ queryKey: ['checklists', 'ranking', qs.toString()], queryFn: () => api<Ranking>(`/api/v1/checklists/ranking?${qs}`), enabled: valid })
  const tq = new URLSearchParams(qs)
  if (branch) tq.set('branch_id', branch)
  const trend = useQuery({ queryKey: ['checklists', 'trend', tq.toString()], queryFn: () => api<TrendPoint[]>(`/api/v1/checklists/trend?${tq}`), enabled: valid })
  const overdue = cov.data?.items.filter((x) => x.overdue).length ?? 0

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader title={t('checklists.report.title')} subtitle={t('checklists.report.subtitle')} backTo="/checklists" backLabel={t('checklists.title')} />
      <Card className="flex flex-wrap items-center gap-3 p-4">
        <Input type="date" value={range.start} max={range.end} onChange={(e) => e.target.value && setRange({ ...range, start: e.target.value })} className="w-40" aria-label={t('schedule.apply.from')} />
        <span className="text-muted">–</span>
        <Input type="date" value={range.end} min={range.start} onChange={(e) => e.target.value && setRange({ ...range, end: e.target.value })} className="w-40" aria-label={t('schedule.apply.to')} />
        <label className="ml-auto flex items-center gap-2 text-sm">
          {t('checklists.report.threshold')}
          <Select className="w-24" value={days} onChange={(e) => setDays(Number(e.target.value))}>
            {[7, 14, 21, 30].map((d) => (
              <option key={d} value={d}>
                {d} {t('checklists.report.daysShort')}
              </option>
            ))}
          </Select>
        </label>
      </Card>
      {!valid && <p role="alert" className="text-sm text-danger">{t('errors.range_invalid')}</p>}
      {!cov.data || !rank.data ? (
        <Skeleton className="h-96" />
      ) : (
        <>
          <Card tint={overdue ? 'rose' : 'mint'} className="p-5">
            <div className="text-xs text-muted">{t('checklists.report.overdueBranches', { days })}</div>
            <div className="mt-1 text-3xl font-semibold tabular-nums">
              {overdue} <span className="text-base font-normal text-muted">/ {cov.data.items.length}</span>
            </div>
          </Card>

          <Card className="overflow-hidden">
            <h2 className="px-5 pt-5 font-semibold">{t('checklists.report.coverage')}</h2>
            <div className="overflow-x-auto">
              <table className="mt-3 w-full text-left text-sm">
                <thead className="border-y border-border text-xs text-muted">
                  <tr>
                    <th className="px-5 py-2.5 font-medium">{t('checklists.branch')}</th>
                    <th className="hidden px-5 py-2.5 font-medium md:table-cell">{t('checklists.coordinator')}</th>
                    <th className="px-5 py-2.5 text-right font-medium">{t('checklists.report.visits')}</th>
                    <th className="px-5 py-2.5 text-right font-medium">{t('checklists.report.avg')}</th>
                    <th className="px-5 py-2.5 font-medium">{t('checklists.report.last')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border tabular-nums">
                  {cov.data.items.map((x) => (
                    <tr key={x.branch.id}>
                      <td className="px-5 py-2.5 font-medium">
                        <button onClick={() => setBranch(String(x.branch.id))} className="text-left hover:text-primary hover:underline" title={t('checklists.report.showTrend')}>
                          {x.branch.name}
                        </button>
                      </td>
                      <td className="hidden px-5 py-2.5 text-muted md:table-cell">{x.coordinator?.name ?? '—'}</td>
                      <td className="px-5 py-2.5 text-right">{x.visits}</td>
                      <td className="px-5 py-2.5 text-right">{x.avg_score === null ? '—' : <Badge tone={scoreTone(x.avg_score)}>{scoreText(x.avg_score)}</Badge>}</td>
                      <td className="px-5 py-2.5">
                        {x.last_at ? (
                          <span className={x.overdue ? 'font-semibold text-danger' : 'text-muted'}>
                            {formatDateTime(x.last_at, i18n.language).slice(0, 10)} · {t('checklists.report.ago', { count: x.days_since ?? 0 })}
                          </span>
                        ) : (
                          <span className="font-semibold text-danger">{t('checklists.report.never')}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                  {cov.data.items.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-5 py-8 text-center text-muted">
                        {t('common.empty')}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </Card>

          <Card className="p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-semibold">{t('checklists.report.trend')}</h2>
              <Select className="w-auto" value={branch} onChange={(e) => setBranch(e.target.value)} aria-label={t('checklists.branch')}>
                <option value="">{t('checklists.report.allBranches')}</option>
                {cov.data.items.map((x) => (
                  <option key={x.branch.id} value={x.branch.id}>
                    {x.branch.name}
                  </option>
                ))}
              </Select>
            </div>
            <Trend points={trend.data ?? []} label={t('checklists.report.trend')} />
          </Card>

          <div className="grid gap-5 md:grid-cols-2">
            <Card className="p-5">
              <h2 className="font-semibold">{t('checklists.report.branchRanking')}</h2>
              <ol className="mt-3 flex flex-col gap-2 text-sm">
                {rank.data.branches.map((b, i) => (
                  <li key={b.id ?? i} className="flex items-center gap-3">
                    <span className="w-5 text-right text-muted tabular-nums">{i + 1}</span>
                    <span className="min-w-0 flex-1 truncate">{b.name ?? '—'}</span>
                    <span className="text-xs text-muted tabular-nums">{b.visits}×</span>
                    <Badge tone={scoreTone(b.avg_score)}>{scoreText(b.avg_score)}</Badge>
                  </li>
                ))}
                {rank.data.branches.length === 0 && <li className="text-muted">{t('common.empty')}</li>}
              </ol>
            </Card>
            <Card className="p-5">
              <h2 className="font-semibold">{t('checklists.report.coordinatorRanking')}</h2>
              <ol className="mt-3 flex flex-col gap-2 text-sm">
                {rank.data.coordinators.map((c, i) => (
                  <li key={c.id ?? i} className="flex items-center gap-3">
                    <span className="w-5 text-right text-muted tabular-nums">{i + 1}</span>
                    <span className="min-w-0 flex-1 truncate">{c.name ?? '—'}</span>
                    <span className="text-xs text-muted tabular-nums">{c.visits}× · {t('checklists.report.branchesN', { count: c.branches })}</span>
                    <Badge tone={scoreTone(c.avg_score)}>{scoreText(c.avg_score)}</Badge>
                  </li>
                ))}
                {rank.data.coordinators.length === 0 && <li className="text-muted">{t('common.empty')}</li>}
              </ol>
            </Card>
          </div>
          <p className="text-xs text-muted">
            <Link to="/checklists" className="hover:underline">
              {t('checklists.title')}
            </Link>
          </p>
        </>
      )}
    </div>
  )
}

/** Haftalik o'rtacha ball chizig'i (0–100). */
function Trend({ points, label }: { points: TrendPoint[]; label: string }) {
  const W = 800
  const H = 180
  const pad = { l: 30, r: 10, t: 10, b: 22 }
  if (points.length === 0) return <p className="py-10 text-center text-sm text-muted">—</p>
  const x = (i: number) => pad.l + (points.length === 1 ? (W - pad.l - pad.r) / 2 : (i * (W - pad.l - pad.r)) / (points.length - 1))
  const y = (v: number) => pad.t + (H - pad.t - pad.b) * (1 - v / 100)
  const pts = points.map((p, i) => [x(i), y(p.avg_score ?? 0)] as const)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mt-3 w-full" role="img" aria-label={label}>
      {[0, 60, 100].map((v) => (
        <g key={v}>
          <line x1={pad.l} x2={W - pad.r} y1={y(v)} y2={y(v)} stroke="var(--border)" strokeDasharray={v === 60 ? '4 4' : undefined} />
          <text x={pad.l - 5} y={y(v) + 3} textAnchor="end" fontSize="10" fill="var(--muted)">{v}</text>
        </g>
      ))}
      <polyline fill="none" stroke="var(--info)" strokeWidth="2" points={pts.map((p) => p.join(',')).join(' ')} />
      {points.map((p, i) => (
        <g key={p.week}>
          <title>{`${p.week.split('-').reverse().join('.')}: ${scoreText(p.avg_score)} (${p.visits}×)`}</title>
          <circle cx={pts[i][0]} cy={pts[i][1]} r="3.5" fill="var(--info)" />
          {(points.length <= 12 || i % Math.ceil(points.length / 12) === 0) && (
            <text x={pts[i][0]} y={H - 6} textAnchor="middle" fontSize="10" fill="var(--muted)">{p.week.slice(8)}.{p.week.slice(5, 7)}</text>
          )}
        </g>
      ))}
    </svg>
  )
}
