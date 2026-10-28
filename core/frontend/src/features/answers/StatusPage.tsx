import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, FileDown, FileSpreadsheet, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { addDays } from '../attendance/api'
import { currentMonth, monthRange, shiftMonth } from '../schedule/api'

interface ReportEvent {
  action: string
  actor: string | null
  level: string | null
  note: string | null
  at: string
}
interface ReportItem {
  id: number
  employee: { id: number; full_name: string }
  branch: { id: number; name: string } | null
  shift: string | null
  coordinator: string | null
  kind: 'day' | 'hourly'
  reason_type: string
  reason: string | null
  start_date: string
  end_date: string
  start_time: string | null
  end_time: string | null
  days: number
  minutes: number | null
  status: Status
  decision_note: string | null
  events: ReportEvent[]
}
type Status = 'pending_coordinator' | 'pending_hr' | 'approved' | 'rejected' | 'cancelled'
interface Report {
  month: string
  kpis: { total: number; people: number } & Record<Status, number>
  days: Record<string, number>
  people: { employee: { id: number; full_name: string }; branch: { name: string } | null; count: number; days: number; hourly: number; hourly_minutes: number }[]
  branches: { id: number; name: string }[]
  total: number
  items: ReportItem[]
}

const TONE: Record<Status, 'warning' | 'success' | 'danger' | 'neutral'> = { pending_coordinator: 'warning', pending_hr: 'warning', approved: 'success', rejected: 'danger', cancelled: 'neutral' }
const CHIPS = ['all', 'pending_coordinator', 'pending_hr', 'approved', 'rejected', 'cancelled'] as const
const BORDER: Record<Status, string> = { pending_coordinator: 'border-l-warning', pending_hr: 'border-l-warning', approved: 'border-l-success', rejected: 'border-l-danger', cancelled: 'border-l-muted' }
const PAGE = 20

function useDuration() {
  const { t } = useTranslation()
  return (it: Pick<ReportItem, 'days' | 'minutes'>) => {
    if (it.minutes === null) return `${it.days} ${t('answersReport.dayUnit')}`
    const h = Math.floor(it.minutes / 60)
    const m = it.minutes % 60
    return [h ? `${h} ${t('answersReport.hourUnit')}` : '', m ? `${m} ${t('answersReport.minUnit')}` : ''].filter(Boolean).join(' ') || '—'
  }
}

/** /answers/holat: javob olish holati: KPI, oy kalendari, xodimlar reytingi, kartochkalar va Excel/PDF eksport. */
export function AnswersStatusPage() {
  const { t, i18n } = useTranslation()
  const dur = useDuration()
  const [month, setMonth] = useState(currentMonth())
  const [status, setStatus] = useState<(typeof CHIPS)[number]>('all')
  const [branch, setBranch] = useState('')
  const [search, setSearch] = useState('')
  const [shown, setShown] = useState(PAGE)
  const lang = i18n.language === 'ru' ? 'ru' : 'uz'
  const base = `month=${month}${branch ? `&branch_id=${branch}` : ''}${search.trim() ? `&q=${encodeURIComponent(search.trim())}` : ''}`
  const q = useQuery({
    queryKey: ['answers', 'report', month, branch, search.trim(), status, shown],
    queryFn: () => api<Report>(`/api/v1/answers/report?${base}&status=${status}&page=1&size=${shown}`),
    placeholderData: (p) => p,
  })
  const d = q.data
  const { start, end } = monthRange(month)
  const cells = useMemo(() => {
    const out: string[] = []
    for (let x = start; x <= end; x = addDays(x, 1)) out.push(x)
    return out
  }, [start, end])
  const lead = (new Date(`${start}T00:00:00Z`).getUTCDay() + 6) % 7
  const mIdx = Number(month.slice(5)) - 1
  const max = Math.max(1, ...Object.values(d?.days ?? {}))
  const reset = () => setShown(PAGE)
  const link = (format: 'xlsx' | 'pdf') => `/api/v1/answers/report/export?${base}&status=${status}&format=${format}&lang=${lang}`
  const kpi = (key: (typeof CHIPS)[number], value: number | undefined) => (
    <button key={key} aria-pressed={status === key} onClick={() => (setStatus(key), reset())} className={'rounded-2xl border p-4 text-left transition-colors ' + (status === key ? 'border-primary bg-primary/5' : 'border-border bg-surface hover:bg-surface-2')}>
      <div className="text-2xl font-semibold tabular-nums">{value ?? '—'}</div>
      <div className="text-xs text-muted">{t(`answersReport.kpi.${key}`)}</div>
    </button>
  )

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader
        title={t('answersReport.title')}
        subtitle={t('answersReport.subtitle')}
        actions={
          <div className="flex gap-2">
            <a href={link('xlsx')} download>
              <Button variant="outline">
                <FileSpreadsheet className="size-4" />
                Excel
              </Button>
            </a>
            <a href={link('pdf')} download>
              <Button variant="outline">
                <FileDown className="size-4" />
                PDF
              </Button>
            </a>
          </div>
        }
      />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {CHIPS.map((k) => kpi(k, k === 'all' ? d?.kpis.total : d?.kpis[k]))}
      </div>

      <Card className="flex flex-col gap-4 p-5">
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="outline" className="size-10 px-0" aria-label={t('schedule.prevMonth')} onClick={() => (setMonth(shiftMonth(month, -1)), reset())}>
            <ChevronLeft className="size-4" />
          </Button>
          <div className="min-w-44 text-center font-semibold">{`${t(`schedule.months.${mIdx}`)} ${month.slice(0, 4)}`}</div>
          <Button variant="outline" className="size-10 px-0" aria-label={t('schedule.nextMonth')} onClick={() => (setMonth(shiftMonth(month, 1)), reset())}>
            <ChevronRight className="size-4" />
          </Button>
          <span className="text-sm text-muted">{d ? t('answersReport.monthLine', { total: d.kpis.total, people: d.kpis.people }) : ''}</span>
        </div>
        <div className="grid grid-cols-7 gap-1.5 text-center text-xs text-muted">
          {[0, 1, 2, 3, 4, 5, 6].map((w) => (
            <div key={w}>{t(`schedule.wd.${w}`)}</div>
          ))}
          {Array.from({ length: lead }, (_, i) => <div key={`l${i}`} />)}
          {cells.map((day) => {
            const n = d?.days[day] ?? 0
            return (
              <div key={day} title={`${day}: ${n}`} className="rounded-lg border border-border py-1.5" style={{ background: n ? `color-mix(in oklab, var(--primary) ${10 + Math.round((n / max) * 45)}%, transparent)` : undefined }}>
                <div className="text-sm font-medium text-text">{Number(day.slice(8))}</div>
                <div className="text-[11px] tabular-nums">{n || ''}</div>
              </div>
            )
          })}
        </div>
      </Card>

      {d && d.people.length > 0 && (
        <Card className="p-5">
          <h2 className="mb-2 font-semibold">{t('answersReport.people')}</h2>
          <ul className="max-h-72 divide-y divide-border overflow-y-auto">
            {d.people.map((p) => (
              <li key={p.employee.id} className="flex items-center justify-between gap-3 py-2.5">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium">{p.employee.full_name}</div>
                  <div className="truncate text-xs text-muted">
                    {[p.branch?.name, `${t('answersReport.dayKind')} ${p.days}`, `${t('answersReport.hourlyKind')} ${p.hourly}`, p.hourly_minutes ? dur({ days: 1, minutes: p.hourly_minutes }) : ''].filter(Boolean).join(' · ')}
                  </div>
                </div>
                <Badge>{t('answersReport.times', { n: p.count })}</Badge>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-56 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
          <Input className="pl-9" placeholder={t('answersReport.search')} value={search} onChange={(e) => (setSearch(e.target.value), reset())} />
        </div>
        {d && d.branches.length > 1 && (
          <Select className="w-56" value={branch} onChange={(e) => (setBranch(e.target.value), reset())} aria-label={t('answersReport.branch')}>
            <option value="">{t('answersReport.allBranches')}</option>
            {d.branches.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </Select>
        )}
      </div>

      {!d ? (
        <Skeleton className="h-48" />
      ) : (
        <div className="flex flex-col gap-3">
          {d.items.map((it) => (
            <Card key={it.id} className={'flex flex-col gap-3 border-l-4 p-4 ' + BORDER[it.status]}>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <div className="font-semibold">{it.employee.full_name}</div>
                  <div className="text-xs text-muted">
                    {it.start_date.split('-').reverse().join('.')}
                    {it.kind === 'hourly' ? ` ${it.start_time}–${it.end_time}` : it.end_date !== it.start_date ? ` – ${it.end_date.split('-').reverse().join('.')}` : ''} · {t(`answersReport.kind.${it.kind}`)} · {dur(it)} · {t(`answersReport.reason.${it.reason_type}`)}
                  </div>
                </div>
                <Badge tone={TONE[it.status]}>{t(`answersReport.kpi.${it.status}`)}</Badge>
              </div>
              <div className="rounded-xl border border-border bg-surface-2 p-3 text-sm">
                <div className="mb-1 text-xs font-semibold">{t('answersReport.where')}</div>
                <div>{t('answersReport.branch')}: {it.branch?.name ?? '—'}</div>
                <div>{t('answersReport.shift')}: {it.shift ?? '—'}</div>
                <div>{t('answersReport.coordinator')}: {it.coordinator ?? '—'}</div>
              </div>
              {it.reason && (
                <div className="rounded-xl border border-warning/40 bg-warning/5 p-3 text-sm">
                  <div className="mb-1 text-xs font-semibold">{t('answersReport.note')}</div>
                  {it.reason}
                </div>
              )}
              <div className="rounded-xl border border-success/30 bg-success/5 p-3 text-sm">
                <div className="mb-1 text-xs font-semibold">{t('answersReport.history')}</div>
                <ul className="flex flex-col gap-0.5">
                  {it.events.map((ev, i) => (
                    <li key={i}>
                      {evText(t, ev)} <span className="text-muted">— {formatDateTime(ev.at, i18n.language)}{ev.actor ? ` · ${ev.actor}` : ''}</span>
                    </li>
                  ))}
                  {it.status === 'pending_hr' && <li className="text-muted">{t('answersReport.awaitingHr')}</li>}
                  {it.status === 'pending_coordinator' && <li className="text-muted">{t('answersReport.awaitingCoord')}</li>}
                </ul>
              </div>
            </Card>
          ))}
          {d.items.length === 0 && <Card className="p-8 text-center text-muted">{t('common.empty')}</Card>}
          {d.total > d.items.length && (
            <Button variant="outline" onClick={() => setShown(shown + PAGE)}>
              {t('answersReport.more', { n: d.total - d.items.length })}
            </Button>
          )}
        </div>
      )}
    </div>
  )
}

function evText(t: (k: string, o?: Record<string, unknown>) => string, ev: ReportEvent): string {
  if (ev.action === 'approved' || ev.action === 'rejected') return `${ev.level ? t(`answersReport.level.${ev.level}`) + ' ' : ''}${t(`answersReport.ev.${ev.action}`)}${ev.note ? ` (${ev.note})` : ''}`
  return t(`answersReport.ev.${ev.action}`, { defaultValue: ev.action })
}
