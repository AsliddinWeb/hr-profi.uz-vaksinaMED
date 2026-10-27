import { useQuery } from '@tanstack/react-query'
import { Download } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { todayLocal } from '../attendance/api'
import { monthRange, shiftMonth } from '../schedule/api'
import { money, type Report } from './api'

type Preset = 'month' | 'lastMonth' | 'custom'

/** /penalties/report: jarimalar hisoboti (xodim, bo'lim, filial yoki tur kesimida) va Excel eksport. */
export function ReportPage() {
  const { t } = useTranslation()
  const [preset, setPreset] = useState<Preset>('month')
  const [groupBy, setGroupBy] = useState('employee')
  const [custom, setCustom] = useState(() => monthRange(todayLocal().slice(0, 7)))
  const today = todayLocal().slice(0, 7)
  const range = preset === 'custom' ? custom : monthRange(preset === 'month' ? today : shiftMonth(today, -1))
  const valid = range.end >= range.start
  const params = new URLSearchParams({ start: range.start, end: range.end, group_by: groupBy })
  const q = useQuery({ queryKey: ['penalties', 'report', params.toString()], queryFn: () => api<Report>(`/api/v1/penalties/report?${params}`), enabled: valid, placeholderData: (p) => p })
  const d = q.data

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader
        title={t('penalties.report.title')}
        subtitle={t('penalties.report.subtitle')}
        actions={
          <a href={`/api/v1/penalties/report/export?${params}`} download aria-disabled={!valid}>
            <Button variant="outline" disabled={!valid}>
              <Download className="size-4" />
              {t('attendance.timesheet.export')}
            </Button>
          </a>
        }
      />
      <Card className="flex flex-wrap items-center gap-3 p-4">
        <div className="flex rounded-control bg-(--seg-bg) p-0.5 text-[13px]" role="group" aria-label={t('attendance.dash.period')}>
          {(['month', 'lastMonth', 'custom'] as const).map((p) => (
            <button key={p} onClick={() => setPreset(p)} aria-pressed={preset === p} className={preset === p ? 'rounded-lg bg-(--seg-on) px-3 py-1.5 font-medium text-text shadow-card' : 'rounded-lg px-3 py-1.5 text-muted transition-colors hover:text-text'}>
              {t(`attendance.dash.presets.${p}`)}
            </button>
          ))}
        </div>
        {preset === 'custom' && (
          <div className="flex items-center gap-2">
            <Input type="date" value={custom.start} onChange={(e) => e.target.value && setCustom({ ...custom, start: e.target.value })} className="w-40" aria-label={t('schedule.apply.from')} />
            <span className="text-muted">–</span>
            <Input type="date" value={custom.end} min={custom.start} onChange={(e) => e.target.value && setCustom({ ...custom, end: e.target.value })} className="w-40" aria-label={t('schedule.apply.to')} />
          </div>
        )}
        <Select className="ml-auto w-auto" value={groupBy} onChange={(e) => setGroupBy(e.target.value)} aria-label={t('penalties.report.groupBy')}>
          {['employee', 'department', 'branch', 'type'].map((g) => (
            <option key={g} value={g}>
              {t(`penalties.report.by.${g}`)}
            </option>
          ))}
        </Select>
      </Card>
      {!d ? (
        <Skeleton className="h-72" />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-4">
            <Stat tint="rose" label={t('penalties.report.approvedSum')} value={money(d.totals.amount)} />
            <Stat tint="sand" label={t('penalties.report.pendingSum')} value={money(d.totals.pending_amount)} />
            <Stat label={t('penalties.report.approvedCount')} value={String(d.totals.approved)} />
            <Stat label={t('penalties.report.blocks')} value={String(d.totals.blocks)} />
          </div>
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-border text-xs text-muted">
                  <tr>
                    <th className="px-5 py-2.5 font-medium">{t('penalties.report.name')}</th>
                    <th className="px-5 py-2.5 text-right font-medium">{t('penalties.status.approved')}</th>
                    <th className="px-5 py-2.5 text-right font-medium">{t('penalties.report.amount')}</th>
                    <th className="hidden px-5 py-2.5 text-right font-medium sm:table-cell">{t('penalties.status.pending')}</th>
                    <th className="hidden px-5 py-2.5 text-right font-medium md:table-cell">{t('penalties.status.cancelled')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border tabular-nums">
                  {d.items.map((r) => (
                    <tr key={String(r.key)}>
                      <td className="px-5 py-2.5 font-medium">{groupBy === 'type' ? t(`letters.incidents.${r.name}`) : (r.name ?? t('attendance.dash.none'))}</td>
                      <td className="px-5 py-2.5 text-right">{r.approved}</td>
                      <td className="px-5 py-2.5 text-right">{money(r.amount)}</td>
                      <td className="hidden px-5 py-2.5 text-right text-muted sm:table-cell">{r.pending}</td>
                      <td className="hidden px-5 py-2.5 text-right text-muted md:table-cell">{r.cancelled}</td>
                    </tr>
                  ))}
                  {d.items.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-5 py-10 text-center text-muted">
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

function Stat({ label, value, tint }: { label: string; value: string; tint?: 'rose' | 'sand' }) {
  return (
    <Card tint={tint} className="p-5">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1.5 text-xl font-semibold tabular-nums">{value}</div>
    </Card>
  )
}
