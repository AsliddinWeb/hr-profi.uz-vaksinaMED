import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Select } from '../../components/ui/Input'
import { api } from '../../lib/api'
import type { BranchPage } from '../branches/api'
import { useCan } from '../auth/useAuth'
import { addDays } from '../attendance/api'
import { currentMonth, monthRange, shiftMonth } from '../schedule/api'
import { period, type CalendarItem } from './api'

/** /answers/calendar: oy kalendari: kim qaysi kuni ruxsat bilan yo'q (kutilayotganlar alohida ko'rsatiladi). */
export function CalendarPage() {
  const { t } = useTranslation()
  const can = useCan()
  const [month, setMonth] = useState(currentMonth())
  const [branchId, setBranchId] = useState('')
  const [selected, setSelected] = useState<string | null>(null)
  const branches = useQuery({ queryKey: ['branches', 'select'], queryFn: () => api<BranchPage>('/api/v1/branches?size=200'), enabled: can('branches.read') })
  const q = useQuery({
    queryKey: ['answers', 'calendar', month, branchId],
    queryFn: () => api<{ items: CalendarItem[] }>(`/api/v1/answers/calendar?month=${month}${branchId ? `&branch_id=${branchId}` : ''}`),
    placeholderData: (p) => p,
  })

  const { start, end } = monthRange(month)
  const days = useMemo(() => {
    const out: string[] = []
    for (let d = start; d <= end; d = addDays(d, 1)) out.push(d)
    return out
  }, [start, end])
  const byDay = useMemo(() => {
    const map = new Map<string, CalendarItem[]>()
    for (const it of q.data?.items ?? []) {
      for (const d of days) if (d >= it.start_date && d <= it.end_date) map.set(d, [...(map.get(d) ?? []), it])
    }
    return map
  }, [q.data, days])
  const lead = (new Date(`${start}T00:00:00Z`).getUTCDay() + 6) % 7
  const m = Number(month.slice(5)) - 1
  const list = selected ? (byDay.get(selected) ?? []) : []

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader title={t('answers.calendar.title')} subtitle={t('answers.calendar.subtitle')} />
      <Card className="flex flex-wrap items-center gap-3 p-4">
        <Button variant="outline" className="size-10 px-0" aria-label={t('schedule.prevMonth')} onClick={() => (setMonth(shiftMonth(month, -1)), setSelected(null))}>
          <ChevronLeft className="size-4" />
        </Button>
        <div className="min-w-40 text-center font-semibold">{`${t(`schedule.months.${m}`)} ${month.slice(0, 4)}`}</div>
        <Button variant="outline" className="size-10 px-0" aria-label={t('schedule.nextMonth')} onClick={() => (setMonth(shiftMonth(month, 1)), setSelected(null))}>
          <ChevronRight className="size-4" />
        </Button>
        {can('branches.read') && (
          <Select className="ml-auto w-auto" value={branchId} onChange={(e) => setBranchId(e.target.value)} aria-label={t('employees.branch')}>
            <option value="">{t('employees.allBranches')}</option>
            {branches.data?.items.map((b) => (
              <option key={b.id} value={b.id}>
                {b.number ? `№${b.number} · ` : ''}
                {b.name}
              </option>
            ))}
          </Select>
        )}
      </Card>

      <Card className="p-4 sm:p-5">
        <div className="grid grid-cols-7 gap-1.5">
          {[0, 1, 2, 3, 4, 5, 6].map((d) => (
            <div key={d} className={'pb-1 text-center text-xs font-medium ' + (d >= 5 ? 'text-danger/80' : 'text-muted')}>
              {t(`schedule.wd.${d}`)}
            </div>
          ))}
          {Array.from({ length: lead }).map((_, i) => (
            <div key={`l${i}`} />
          ))}
          {days.map((d) => {
            const items = byDay.get(d) ?? []
            const approved = items.filter((i) => i.status === 'approved').length
            const pending = items.length - approved
            return (
              <button key={d} type="button" onClick={() => setSelected(d === selected ? null : d)} aria-pressed={selected === d} className={'flex min-h-16 flex-col items-start gap-1 rounded-control border p-1.5 text-left sm:min-h-20 ' + (selected === d ? 'border-primary bg-primary/10' : 'border-border hover:bg-surface-2')}>
                <span className="text-xs font-semibold tabular-nums">{Number(d.slice(8))}</span>
                <span className="flex flex-wrap gap-1">
                  {approved > 0 && <span className="rounded-full bg-success/15 px-1.5 text-[11px] font-semibold text-success" title={t('answers.status.approved')}>{approved}</span>}
                  {pending > 0 && <span className="rounded-full bg-warning/20 px-1.5 text-[11px] font-semibold text-warning" title={t('answers.inbox.pending')}>{pending}</span>}
                </span>
              </button>
            )
          })}
        </div>
        <div className="mt-4 flex flex-wrap gap-4 text-xs text-muted">
          <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-success" />{t('answers.status.approved')}</span>
          <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-warning" />{t('answers.inbox.pending')}</span>
        </div>
      </Card>

      {selected && (
        <Card className="p-5">
          <h2 className="font-semibold">{selected.split('-').reverse().join('.')}</h2>
          <ul className="mt-3 divide-y divide-border text-sm">
            {list.map((i) => (
              <li key={i.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
                <Link to={`/answers/${i.id}`} className="font-medium hover:text-primary hover:underline">
                  {i.employee.full_name}
                </Link>
                <span className="text-muted">
                  {period(i)} · {t(`answers.reason.${i.reason_type}`)} · {t(`answers.status.${i.status}`)}
                </span>
              </li>
            ))}
            {list.length === 0 && <li className="py-3 text-muted">{t('common.empty')}</li>}
          </ul>
        </Card>
      )}
    </div>
  )
}
