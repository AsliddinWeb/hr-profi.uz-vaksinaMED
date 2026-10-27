import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Send } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { PageHeader } from '../../../components/layout/PageHeader'
import { Badge } from '../../../components/ui/Badge'
import { Button } from '../../../components/ui/Button'
import { Card } from '../../../components/ui/Card'
import { Input } from '../../../components/ui/Input'
import { Skeleton } from '../../../components/ui/Skeleton'
import { useToast } from '../../../components/ui/toastContext'
import { api, send } from '../../../lib/api'
import { formatDate, formatDateTime } from '../../../lib/format'
import { errorText } from '../../auth/errorText'
import { todayLocal } from '../api'

interface Explanation {
  id: number
  status: 'pending' | 'submitted'
  reason: string | null
  measures: string | null
  due_at: string
  overdue: boolean
}
interface Item {
  employee_id: number
  full_name: string
  position: string | null
  branch: string
  kind: 'absent' | 'late'
  arrived: string | null
  streak: number
  anomaly: string | null
  month: { date: string; kind: 'absent' | 'late'; arrived: string | null }[]
  explanation: Explanation | null
}
interface Shift {
  name: string
  start: string | null
  end: string | null
  absent: Item[]
  late: Item[]
}
interface Report {
  date: string
  time: string
  coordinators: { user_id: number; name: string; absent: number; late: number; shifts: Shift[] }[]
  long_absent: unknown[]
  pending: number
  overdue: number
  can_send: boolean
}

/** /attendance/coordinator-report: koordinator x smena kesimida kelmagan/kechikkanlar va sabab/chora izohi. */
export function CoordReportPage() {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const [date, setDate] = useState(todayLocal)
  const q = useQuery({ queryKey: ['coord-report', date], queryFn: () => api<Report>(`/api/v1/coord-report?date=${date}`), refetchInterval: 120_000 })
  const sendNow = useMutation({
    mutationFn: () => send<{ sent: number }>('POST', '/api/v1/coord-report/send'),
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['coord-report'] })
      toast.push({ title: t('coordReport.sent', { n: r.sent }), tone: 'success' })
    },
  })
  const r = q.data

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader
        title={t('coordReport.title')}
        subtitle={r ? t('coordReport.subtitle', { date: formatDate(r.date, i18n.language), time: r.time }) : undefined}
        actions={
          r?.can_send && (
            <Button variant="outline" disabled={sendNow.isPending} onClick={() => sendNow.mutate()}>
              <Send className="size-4" />
              {t('coordReport.sendNow')}
            </Button>
          )
        }
      />
      <div className="flex flex-wrap items-center gap-3">
        <Input type="date" value={date} max={todayLocal()} onChange={(e) => setDate(e.target.value)} className="w-auto" aria-label={t('attendance.date')} />
        {r && r.pending > 0 && <Badge tone="warning">{t('coordReport.pending', { n: r.pending })}</Badge>}
        {r && r.overdue > 0 && <Badge tone="danger">{t('coordReport.overdue', { n: r.overdue })}</Badge>}
      </div>
      {sendNow.isError && <p role="alert" className="text-sm text-danger">{errorText(t, sendNow.error)}</p>}
      {q.isLoading && <Skeleton className="h-48" />}
      {r && r.coordinators.length === 0 && <Card className="p-8 text-center text-muted">{t('coordReport.empty')}</Card>}
      {r?.coordinators.map((c) => (
        <Card key={c.user_id} className="flex flex-col gap-4 p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-lg font-semibold">{c.name}</h2>
            <div className="flex gap-2">
              <Badge tone="danger">{t('coordReport.absent')}: {c.absent}</Badge>
              <Badge tone="warning">{t('coordReport.late')}: {c.late}</Badge>
            </div>
          </div>
          {c.shifts.map((s) => (
            <section key={s.name + s.start} className="flex flex-col gap-2">
              <h3 className="text-sm font-medium text-muted">
                🕘 {s.name} ({s.start}–{s.end})
              </h3>
              {[...s.absent, ...s.late].map((it) => (
                <Row key={it.employee_id + it.kind} item={it} date={r.date} />
              ))}
            </section>
          ))}
        </Card>
      ))}
    </div>
  )
}

function Row({ item, date }: { item: Item; date: string }) {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState(item.explanation?.reason ?? '')
  const [measures, setMeasures] = useState(item.explanation?.measures ?? '')
  const save = useMutation({
    mutationFn: () => send('POST', '/api/v1/coord-report/explain', { employee_id: item.employee_id, work_date: date, kind: item.kind, reason, measures }),
    onSuccess: () => {
      setOpen(false)
      void qc.invalidateQueries({ queryKey: ['coord-report'] })
      toast.push({ title: t('coordReport.saved'), tone: 'success' })
    },
  })
  const x = item.explanation
  return (
    <div className="rounded-control border border-border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="font-medium">{item.full_name}</div>
          <div className="text-xs text-muted">
            {[item.position, item.branch].filter(Boolean).join(' · ')}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge tone={item.kind === 'absent' ? 'danger' : 'warning'}>{item.kind === 'absent' ? t('coordReport.absentOne') : t('coordReport.lateAt', { time: item.arrived })}</Badge>
          {item.streak >= 3 && item.kind === 'absent' && <Badge tone="danger">{t('coordReport.streak', { n: item.streak })}</Badge>}
          {item.anomaly && <Badge>{t('coordReport.anomaly')}</Badge>}
          {x?.status === 'submitted' ? <Badge tone="success">{t('coordReport.explained')}</Badge> : x?.overdue ? <Badge tone="danger">{t('coordReport.overdueOne')}</Badge> : <Badge tone="warning">{t('coordReport.needExplain')}</Badge>}
        </div>
      </div>
      {item.month.length > 1 && (
        <p className="mt-2 text-xs text-muted">
          {t('coordReport.month')}{item.month.length > 7 ? ` (${item.month.length})` : ''}: {item.month.length > 7 ? '… ' : ''}{item.month.slice(-7).map((m) => `${formatDate(m.date, i18n.language).slice(0, 5)} ${m.kind === 'absent' ? t('coordReport.absentShort') : t('coordReport.lateShort', { time: m.arrived })}`).join(' · ')}
        </p>
      )}
      {x?.status === 'submitted' && !open && (
        <div className="mt-2 text-sm">
          <p><span className="text-muted">{t('coordReport.reason')}:</span> {x.reason}</p>
          <p><span className="text-muted">{t('coordReport.measures')}:</span> {x.measures}</p>
        </div>
      )}
      {x && x.status === 'pending' && <p className="mt-2 text-xs text-muted">{t('coordReport.due', { time: formatDateTime(x.due_at, i18n.language) })}</p>}
      {!open ? (
        <Button variant="outline" className="mt-2" onClick={() => setOpen(true)}>
          {x?.status === 'submitted' ? t('coordReport.edit') : t('coordReport.write')}
        </Button>
      ) : (
        <div className="mt-3 flex flex-col gap-2">
          <label className="text-xs text-muted">{t('coordReport.reason')}</label>
          <textarea value={reason} onChange={(e) => setReason(e.target.value)} maxLength={1000} rows={2} className="w-full rounded-control border border-border bg-surface px-3 py-2 text-sm" />
          <label className="text-xs text-muted">{t('coordReport.measures')}</label>
          <textarea value={measures} onChange={(e) => setMeasures(e.target.value)} maxLength={1000} rows={2} className="w-full rounded-control border border-border bg-surface px-3 py-2 text-sm" />
          {save.isError && <p role="alert" className="text-sm text-danger">{errorText(t, save.error)}</p>}
          <div className="flex gap-2">
            <Button disabled={save.isPending || reason.trim().length < 3 || measures.trim().length < 3} onClick={() => save.mutate()}>
              {t('common.save')}
            </Button>
            <Button variant="outline" onClick={() => setOpen(false)}>
              {t('common.cancel')}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
