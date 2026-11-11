import { useQuery } from '@tanstack/react-query'
import { Download, Search } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input, Select } from '../../components/ui/Input'
import { api } from '../../lib/api'
import { PayrollTabs } from './PayrollTabs'

type Row = Record<string, number | string | null> & { id: number; name: string }
type Sheet = { period: string; prev_period: string; status: string; count: number; totals: { plan: number; prev_plan: number; sales: number; over_plan: number; to_pay: number; vs_prev_pct: number | null }; positions: { id: number; name: string }[]; items: Row[] }

const COLS = ['plan', 'prev_plan', 'sales', 'over_plan', 'plan_pct', 'commission_percent', 'commission', 'fixed', 'plan_bonus', 'kpi_bonus', 'advance', 'recalc', 'time_penalty', 'due_penalty', 'gross', 'to_pay'] as const
const money = (v: unknown) => (typeof v === 'number' ? Math.round(v).toLocaleString('ru-RU') : '—')

/** /payroll/sheet — Xodimlar oylik hisobi (savdo, reja, fiks, bonus va jarimalar) — vaksinahr "Oylik hisob" ko'rinishi. */
export function SalesSheetPage() {
  const { t } = useTranslation()
  const runs = useQuery({ queryKey: ['payroll', 'runs'], queryFn: () => api<{ id: number; period: string; status: string }[]>('/api/v1/payroll/runs') })
  const [rid, setRid] = useState<number | null>(null)
  const run = rid ?? runs.data?.[0]?.id ?? null
  const [q, setQ] = useState('')
  const [pos, setPos] = useState(0)
  const qs = new URLSearchParams({ ...(q ? { q } : {}), ...(pos ? { position_id: String(pos) } : {}) }).toString()
  const d = useQuery({ queryKey: ['payroll', 'sheet', run, qs], enabled: !!run, queryFn: () => api<Sheet>(`/api/v1/payroll/runs/${run}/sheet?${qs}`) })
  const s = d.data
  const cards: [string, string][] = s
    ? [
        [t('sheet.c.employees'), `${s.count}`],
        [t('sheet.c.plan', { p: s.period }), money(s.totals.plan)],
        [t('sheet.c.prevPlan', { p: s.prev_period }), money(s.totals.prev_plan)],
        [t('sheet.c.sales'), money(s.totals.sales)],
        [t('sheet.c.over'), money(s.totals.over_plan)],
        [t('sheet.c.vsPrev', { p: s.prev_period }), s.totals.vs_prev_pct != null ? `${s.totals.vs_prev_pct}%` : '—'],
        [t('sheet.c.toPay'), money(s.totals.to_pay)],
      ]
    : []
  return (
    <div className="flex flex-col gap-5">
      <div>
        <div className="text-[11px] font-semibold uppercase tracking-wider text-muted">{t('sheet.kicker')}</div>
        <h1 className="text-2xl font-semibold tracking-tight">{t('sheet.title')}</h1>
        <p className="text-sm text-muted">{t('sheet.subtitle')}</p>
      </div>
      <PayrollTabs />
      <div className="flex flex-wrap items-center gap-2">
        <Select value={run ?? ''} onChange={(e) => setRid(Number(e.target.value))} aria-label={t('sheet.period')}>
          {runs.data?.map((r) => <option key={r.id} value={r.id}>{r.period} · {t(`payroll.status.${r.status}`, r.status)}</option>)}
        </Select>
        <Select value={pos} onChange={(e) => setPos(Number(e.target.value))} aria-label={t('sheet.position')}>
          <option value={0}>{t('sheet.allPositions')}</option>
          {s?.positions.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </Select>
        <div className="relative min-w-56 flex-1">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
          <Input className="pl-9" placeholder={t('sheet.search')} value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        {run && <a href={`/api/v1/payroll/runs/${run}/sheet.xlsx?${qs}`}><Button variant="outline"><Download className="size-4" />Excel</Button></a>}
      </div>
      {!runs.data?.length && <Card className="p-8 text-center text-sm text-muted">{t('sheet.noRuns')}</Card>}
      {s && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
            {cards.map(([l, v]) => <Card key={l} className="p-3"><div className="text-[11px] font-semibold uppercase text-muted">{l}</div><div className="font-mono text-lg font-semibold">{v}</div></Card>)}
          </div>
          <Card className="overflow-x-auto">
            <table className="w-full whitespace-nowrap text-[13px]">
              <thead className="text-left text-[10px] uppercase tracking-wider text-muted">
                <tr>
                  <th className="sticky left-0 bg-surface p-2">№</th>
                  <th className="sticky left-8 bg-surface p-2">{t('sheet.col.name')}</th>
                  <th className="p-2">{t('sheet.col.position')}</th>
                  <th className="p-2">{t('sheet.col.phone')}</th>
                  {COLS.map((c) => <th key={c} className="p-2 text-right">{t(`sheet.col.${c}`)}</th>)}
                </tr>
              </thead>
              <tbody>
                {s.items.map((r, i) => (
                  <tr key={r.id} className="border-t border-border">
                    <td className="sticky left-0 bg-surface p-2 text-muted">{i + 1}</td>
                    <td className="sticky left-8 bg-surface p-2 font-medium">{r.name}</td>
                    <td className="p-2">{r.position ?? '—'}</td>
                    <td className="p-2">{r.phone ?? '—'}</td>
                    {COLS.map((c) => (
                      <td key={c} className={`p-2 text-right font-mono ${(c === 'time_penalty' || c === 'due_penalty') && Number(r[c]) > 0 ? 'text-danger' : ''} ${c === 'to_pay' ? 'font-semibold' : ''}`}>
                        {c === 'plan_pct' || c === 'commission_percent' ? (r[c] != null ? `${r[c]}%` : '—') : money(r[c])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {!s.items.length && <p className="p-8 text-center text-sm text-muted">{t('sheet.empty')}</p>}
          </Card>
        </>
      )}
    </div>
  )
}
