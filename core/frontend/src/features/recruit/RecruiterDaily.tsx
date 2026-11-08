import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Card } from '../../components/ui/Card'
import { Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'

const COLS = ['received', 'attached', 'calls', 'invited', 'came', 'hired'] as const
type Col = (typeof COLS)[number]
interface Daily {
  days: ({ date: string } & Record<Col, number>)[]
  total: Record<Col, number>
  by_source: { source: string; count: number }[]
  recruiters: { id: number; name: string }[]
}

/** Rekruterning kunlik nazorati: kuniga nechta rezyume keldi, nechtasi biriktirildi, qo'ng'iroqlar, chaqirilgan/kelgan va qaysi e'lon orqali. */
export function RecruiterDaily({ from, to }: { from: string; to: string }) {
  const { t } = useTranslation()
  const [rid, setRid] = useState('')
  const q = useQuery({
    queryKey: ['recruit', 'daily', from, to, rid],
    queryFn: () => api<Daily>(`/api/v1/recruit/daily?start=${from}&end=${to}${rid ? `&recruiter_id=${rid}` : ''}`),
    placeholderData: (p) => p,
  })
  const d = q.data
  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="font-semibold">{t('rdaily.title')}</h3>
        <Select value={rid} onChange={(e) => setRid(e.target.value)} className="ml-auto w-56" aria-label={t('rdaily.recruiter')}>
          <option value="">{t('rdaily.all')}</option>
          {(d?.recruiters ?? []).map((r) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </Select>
      </div>
      {!d ? (
        <Skeleton className="h-40" />
      ) : (
        <>
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
            {COLS.map((c) => (
              <div key={c} className="rounded-control bg-surface-2 p-3">
                <div className="text-xl font-bold tabular-nums">{d.total[c]}</div>
                <div className="text-xs text-muted">{t(`rdaily.c.${c}`)}</div>
              </div>
            ))}
          </div>
          {d.total.invited > 0 && <p className="text-xs text-muted">{t('rdaily.conv', { p: Math.round((d.total.came / d.total.invited) * 100) })}</p>}
          <div className="grid gap-4 lg:grid-cols-[1fr_16rem]">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-xs text-muted">
                  <tr>
                    <th className="py-1.5 text-left font-medium">{t('rdash.date')}</th>
                    {COLS.map((c) => (
                      <th key={c} className="py-1.5 text-right font-medium">
                        {t(`rdaily.c.${c}`)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border tabular-nums">
                  {[...d.days].reverse().map((x) => (
                    <tr key={x.date} className={COLS.every((c) => !x[c]) ? 'text-muted/60' : ''}>
                      <td className="py-1.5">{x.date}</td>
                      {COLS.map((c) => (
                        <td key={c} className={`py-1.5 text-right ${c === 'came' && x.came ? 'font-semibold text-emerald-600' : ''}`}>
                          {x[c] || '·'}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">{t('rdaily.bySource')}</h4>
              {d.by_source.length === 0 && <p className="text-sm text-muted">—</p>}
              {d.by_source.map((s) => (
                <div key={s.source} className="mb-2">
                  <div className="flex justify-between text-sm">
                    <span className="truncate">{s.source}</span>
                    <span className="font-semibold tabular-nums">{s.count}</span>
                  </div>
                  <div className="mt-1 h-1.5 rounded-full bg-surface-2">
                    <div className="h-full rounded-full bg-primary" style={{ width: `${(s.count / Math.max(1, d.by_source[0].count)) * 100}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </Card>
  )
}
