import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { PageHeader } from '../../components/layout/PageHeader'
import { Card } from '../../components/ui/Card'
import { Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { shortMoney, type Stats } from './api'

/** /crm/report: voronka, yutilgan/yo'qotilgan, konversiya, kutilayotgan daromad, yo'qotish sabablari, eng yaxshi sotuvchilar. */
export function CrmReportPage() {
  const { t, i18n } = useTranslation()
  const [days, setDays] = useState(30)
  const q = useQuery({ queryKey: ['crm', 'stats', days], queryFn: () => api<Stats>(`/api/v1/crm/stats?days=${days}`) })
  const s = q.data
  const max = Math.max(1, ...(s?.funnel.map((f) => f.count) ?? [1]))
  const m = (n: number) => `${shortMoney(n, i18n.language)} UZS`
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <PageHeader
        title={t('crm.report.title')}
        actions={
          <Select value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label={t('crm.report.period')} className="w-40">
            {[7, 30, 90, 365].map((d) => (
              <option key={d} value={d}>
                {t('crm.report.lastDays', { n: d })}
              </option>
            ))}
          </Select>
        }
      />
      {!s ? (
        <Skeleton className="h-96" />
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[
              [t('crm.report.new'), String(s.new)],
              [t('crm.report.won'), `${s.won} · ${m(s.won_amount)}`],
              [t('crm.report.winRate'), s.win_rate === null ? '—' : `${s.win_rate}%`],
              [t('crm.report.weighted'), m(s.weighted_pipeline)],
            ].map(([k, v]) => (
              <Card key={k} className="p-4">
                <div className="text-xs text-muted">{k}</div>
                <div className="mt-1 text-xl font-semibold tabular-nums">{v}</div>
              </Card>
            ))}
          </div>
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
            <Card className="flex flex-col gap-3 p-5">
              <h2 className="font-semibold">{t('crm.report.funnel')}</h2>
              {s.funnel.map((f) => (
                <div key={f.id} className="grid grid-cols-[8rem_minmax(0,1fr)_7rem] items-center gap-3 text-sm">
                  <span className="truncate">{f.name}</span>
                  <div className="h-6 overflow-hidden rounded-md bg-surface-2">
                    <div className={'flex h-full items-center rounded-md px-2 text-xs font-medium text-white ' + (f.is_won ? 'bg-success' : 'bg-primary')} style={{ width: `${Math.max(6, (f.count / max) * 100)}%` }}>
                      {f.count}
                    </div>
                  </div>
                  <span className="text-right text-xs tabular-nums text-muted">{m(f.total)}</span>
                </div>
              ))}
              <p className="text-xs text-muted">
                {t('crm.report.lost')}: {s.lost} · {t('crm.report.overdue')}: <span className={s.overdue_activities ? 'font-semibold text-danger' : ''}>{s.overdue_activities}</span>
              </p>
            </Card>
            <div className="flex flex-col gap-4">
              <Card className="p-5">
                <h2 className="mb-2 font-semibold">{t('crm.report.topOwners')}</h2>
                <ol className="flex flex-col gap-1.5 text-sm">
                  {s.top_owners.map((o, i) => (
                    <li key={i} className="flex justify-between gap-2">
                      <span className="truncate">
                        {i + 1}. {o.name}
                      </span>
                      <span className="tabular-nums text-muted">
                        {o.won} · {m(o.amount)}
                      </span>
                    </li>
                  ))}
                  {s.top_owners.length === 0 && <li className="text-muted">—</li>}
                </ol>
              </Card>
              <Card className="p-5">
                <h2 className="mb-2 font-semibold">{t('crm.report.lostReasons')}</h2>
                <ul className="flex flex-col gap-1.5 text-sm">
                  {s.lost_reasons.map((r) => (
                    <li key={r.reason} className="flex justify-between gap-2">
                      <span className="truncate">{r.reason}</span>
                      <span className="tabular-nums text-muted">{r.count}</span>
                    </li>
                  ))}
                  {s.lost_reasons.length === 0 && <li className="text-muted">—</li>}
                </ul>
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
