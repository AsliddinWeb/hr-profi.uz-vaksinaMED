import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { PageHeader } from '../../components/layout/PageHeader'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { addDays, todayLocal } from '../attendance/api'
import { Dist, Kpi } from '../tasks/AnalyticsPage'
import { avgText, type Analytics } from './api'

/** /canteen/analytics: o'rtacha baho, taqsimot, kunlik dinamika va taomlar reytingi. */
export function AnalyticsPage() {
  const { t } = useTranslation()
  const today = todayLocal()
  const [range, setRange] = useState({ start: addDays(today, -29), end: today })
  const valid = range.end >= range.start && (new Date(range.end).getTime() - new Date(range.start).getTime()) / 86400000 <= 366
  const q = useQuery({ queryKey: ['canteen', 'analytics', range.start, range.end], queryFn: () => api<Analytics>(`/api/v1/canteen/analytics?start=${range.start}&end=${range.end}`), enabled: valid, placeholderData: (p) => p })
  const d = q.data
  const k = d?.kpis
  const pct = (v: number | null | undefined) => (v === null || v === undefined ? '—' : `${(v * 100).toFixed(0)}%`)
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader title={t('canteen.analytics.title')} subtitle={t('canteen.analytics.subtitle')} />
      <Card className="flex flex-wrap items-center gap-3 p-4">
        <Input type="date" value={range.start} max={range.end} onChange={(e) => e.target.value && setRange({ ...range, start: e.target.value })} className="w-40" aria-label={t('schedule.apply.from')} />
        <span className="text-muted">–</span>
        <Input type="date" value={range.end} min={range.start} onChange={(e) => e.target.value && setRange({ ...range, end: e.target.value })} className="w-40" aria-label={t('schedule.apply.to')} />
      </Card>
      {!valid && <p role="alert" className="text-sm text-danger">{t('errors.range_invalid')}</p>}
      {!d || !k ? (
        <Skeleton className="h-96" />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Kpi tint="mint" label={t('canteen.avgRating')} value={avgText(k.avg)} hint={t('canteen.ratingsN', { count: k.ratings })} />
            <Kpi tint="lilac" label={t('canteen.analytics.participation')} value={`${k.raters} / ${k.active_employees}`} hint={t('canteen.analytics.viaQr', { count: k.via_qr })} />
            <Kpi tint="rose" label={t('canteen.analytics.low')} value={pct(k.low_share)} hint="≤ 2 ★" />
            <Kpi label={t('canteen.analytics.comments')} value={String(k.commented)} hint={t('canteen.analytics.unanswered', { count: k.unanswered })} />
          </div>
          <div className="grid gap-5 md:grid-cols-2">
            <Dist title={t('canteen.analytics.distribution')} rows={[5, 4, 3, 2, 1].map((s) => [`${s} ★`, d.distribution[String(s)] ?? 0])} />
            <Card className="p-5">
              <h2 className="font-semibold">{t('canteen.analytics.trend')}</h2>
              <Trend trend={d.trend} label={t('canteen.analytics.trend')} />
            </Card>
          </div>
          <Card className="overflow-hidden">
            <h2 className="px-5 pt-5 font-semibold">{t('canteen.analytics.dishes')}</h2>
            <div className="overflow-x-auto">
              <table className="mt-3 w-full text-left text-sm">
                <thead className="border-y border-border text-xs text-muted">
                  <tr>
                    <th className="px-5 py-2.5 font-medium">{t('canteen.menus.dishName')}</th>
                    <th className="hidden px-5 py-2.5 font-medium sm:table-cell">{t('canteen.menus.kind')}</th>
                    <th className="px-5 py-2.5 text-right font-medium">{t('canteen.avgRating')}</th>
                    <th className="px-5 py-2.5 text-right font-medium">{t('canteen.analytics.votes')}</th>
                    <th className="hidden px-5 py-2.5 text-right font-medium sm:table-cell">{t('canteen.analytics.days')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border tabular-nums">
                  {d.dishes.map((x) => (
                    <tr key={x.name}>
                      <td className="px-5 py-2.5 font-medium">{x.name}</td>
                      <td className="hidden px-5 py-2.5 text-muted sm:table-cell">{t(`canteen.kind.${x.kind}`)}</td>
                      <td className={'px-5 py-2.5 text-right font-medium ' + (x.avg < 3 ? 'text-danger' : x.avg >= 4 ? 'text-success' : '')}>{x.avg.toFixed(1)}</td>
                      <td className="px-5 py-2.5 text-right">{x.count}</td>
                      <td className="hidden px-5 py-2.5 text-right text-muted sm:table-cell">{x.days}</td>
                    </tr>
                  ))}
                  {d.dishes.length === 0 && (
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
        </>
      )}
    </div>
  )
}

/** Kunlik o'rtacha baho chizig'i (1–5). */
function Trend({ trend, label }: { trend: Analytics['trend']; label: string }) {
  const W = 400
  const H = 160
  const pad = { l: 22, r: 8, t: 8, b: 20 }
  const pts = trend.filter((p) => p.avg !== null)
  if (pts.length === 0) return <p className="py-10 text-center text-sm text-muted">—</p>
  const x = (i: number) => pad.l + (trend.length === 1 ? (W - pad.l - pad.r) / 2 : (i * (W - pad.l - pad.r)) / (trend.length - 1))
  const y = (v: number) => pad.t + (H - pad.t - pad.b) * (1 - (v - 1) / 4)
  const line = trend.map((p, i) => (p.avg === null ? null : `${x(i)},${y(p.avg)}`)).filter(Boolean).join(' ')
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mt-3 w-full" role="img" aria-label={label}>
      {[1, 3, 5].map((v) => (
        <g key={v}>
          <line x1={pad.l} x2={W - pad.r} y1={y(v)} y2={y(v)} stroke="var(--border)" />
          <text x={pad.l - 4} y={y(v) + 3} textAnchor="end" fontSize="9" fill="var(--muted)">{v}</text>
        </g>
      ))}
      <polyline fill="none" stroke="var(--info)" strokeWidth="2" points={line} />
      {trend.map((p, i) =>
        p.avg === null ? null : (
          <g key={p.date}>
            <title>{`${p.date.split('-').reverse().join('.')}: ${p.avg} (${p.count})`}</title>
            <circle cx={x(i)} cy={y(p.avg)} r="3" fill="var(--info)" />
          </g>
        ),
      )}
    </svg>
  )
}
