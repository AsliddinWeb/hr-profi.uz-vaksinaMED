import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { api } from '../../lib/api'
import { addDays } from '../attendance/api'
import { currentMonth, monthRange, shiftMonth } from '../schedule/api'
import { Filters } from './Filters'
import { defaultFilter, type TaskFilter } from './filterState'
import { ViewTabs } from './ViewTabs'
import { dueText, PRIORITY_TONE, type TaskItem } from './api'

/** /tasks/calendar: muddati shu oyga to'g'ri kelgan topshiriqlar. */
export function CalendarPage() {
  const { t } = useTranslation()
  const [month, setMonth] = useState(currentMonth())
  const [filter, setFilter] = useState<TaskFilter>(defaultFilter)
  const [selected, setSelected] = useState<string | null>(null)
  const q = useQuery({ queryKey: ['tasks', 'calendar', month, filter.scope], queryFn: () => api<{ items: TaskItem[] }>(`/api/v1/tasks/calendar?month=${month}&scope=${filter.scope}`), placeholderData: (p) => p })
  const { start, end } = monthRange(month)
  const days = useMemo(() => {
    const out: string[] = []
    for (let d = start; d <= end; d = addDays(d, 1)) out.push(d)
    return out
  }, [start, end])
  const byDay = useMemo(() => {
    const map = new Map<string, TaskItem[]>()
    for (const it of q.data?.items ?? []) {
      const day = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Tashkent' }).format(new Date(it.due_at as string))
      map.set(day, [...(map.get(day) ?? []), it])
    }
    return map
  }, [q.data])
  const lead = (new Date(`${start}T00:00:00Z`).getUTCDay() + 6) % 7
  const list = selected ? (byDay.get(selected) ?? []) : []

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <PageHeader title={t('tasks.title')} subtitle={t('tasks.subtitle')} actions={<ViewTabs />} />
      <Card className="flex flex-wrap items-center gap-3 p-3">
        <Button variant="outline" className="size-10 px-0" aria-label={t('schedule.prevMonth')} onClick={() => (setMonth(shiftMonth(month, -1)), setSelected(null))}>
          <ChevronLeft className="size-4" />
        </Button>
        <div className="min-w-40 text-center font-semibold">{`${t(`schedule.months.${Number(month.slice(5)) - 1}`)} ${month.slice(0, 4)}`}</div>
        <Button variant="outline" className="size-10 px-0" aria-label={t('schedule.nextMonth')} onClick={() => (setMonth(shiftMonth(month, 1)), setSelected(null))}>
          <ChevronRight className="size-4" />
        </Button>
        <div className="ml-auto flex flex-wrap items-center gap-3">
          <Filters value={filter} onChange={setFilter} />
        </div>
      </Card>
      <Card className="p-4">
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
            return (
              <button key={d} type="button" onClick={() => setSelected(d === selected ? null : d)} aria-pressed={selected === d} className={'flex min-h-20 flex-col gap-1 rounded-control border p-1.5 text-left ' + (selected === d ? 'border-primary bg-primary/10' : 'border-border hover:bg-surface-2')}>
                <span className="text-xs font-semibold tabular-nums">{Number(d.slice(8))}</span>
                {items.slice(0, 2).map((i) => (
                  <span key={i.id} className={`truncate rounded px-1 text-[11px] ${i.overdue ? 'bg-danger/15 text-danger' : i.status === 'done' ? 'bg-success/15 text-success line-through' : PRIORITY_TONE[i.priority]}`}>
                    {i.title}
                  </span>
                ))}
                {items.length > 2 && <span className="text-[11px] text-muted">+{items.length - 2}</span>}
              </button>
            )
          })}
        </div>
      </Card>
      {selected && (
        <Card className="p-5">
          <h2 className="font-semibold">{selected.split('-').reverse().join('.')}</h2>
          <ul className="mt-3 divide-y divide-border text-sm">
            {list.map((i) => (
              <li key={i.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
                <Link to={`/tasks/${i.id}`} className="font-medium hover:text-primary hover:underline">
                  {i.title}
                </Link>
                <span className="text-muted">
                  {dueText(i.due_at)} · {i.assignee?.name ?? '—'} · {t(`tasks.status.${i.status}`)}
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
