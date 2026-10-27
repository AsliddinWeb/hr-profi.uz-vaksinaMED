import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { useToast } from '../../components/ui/toastContext'
import { api, send } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { errorText } from '../auth/errorText'

interface Day {
  day_no: number
  seen: string | null
  understood: string | null
  done: string | null
  open: boolean
  feedback: { id: number; role: string; text: string; author: string | null; created_at: string }[]
}
interface Daily {
  today: number
  days: Day[]
  decision: { value: 'fit' | 'not_fit' | null; note: string | null; at: string | null; next_enrollment_id: number | null }
  can: { report: boolean; feedback: boolean; decide: boolean; package: boolean }
}
const area = 'w-full rounded-control border border-border bg-surface px-3 py-2 text-sm'

/** Preboarding 7 kun: kunlik hisobot, fidbek, filial paketi va 7-kun qarori. */
export function DailyPanel({ enrollmentId }: { enrollmentId: number }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const base = `/api/v1/internship/enrollments/${enrollmentId}`
  const q = useQuery({ queryKey: ['internship', 'daily', enrollmentId], queryFn: () => api<Daily>(`${base}/daily`), refetchInterval: 60_000 })
  const [note, setNote] = useState('')
  const refresh = () => void qc.invalidateQueries({ queryKey: ['internship'] })
  const decide = useMutation({
    mutationFn: (decision: 'fit' | 'not_fit') => send<{ next_enrollment_id: number | null; onboarding_program_missing: boolean }>('POST', `${base}/decision`, { decision, note: note || null }),
    onSuccess: (r) => {
      refresh()
      toast.push({ title: r.onboarding_program_missing ? t('onboarding.noProgram') : t('onboarding.decided'), tone: r.onboarding_program_missing ? 'warning' : 'success' })
    },
  })
  const pkg = useMutation({ mutationFn: () => send<{ sent: number }>('POST', `${base}/package`), onSuccess: (r) => toast.push({ title: t('onboarding.packageSent', { n: r.sent }), tone: 'success' }) })
  const d = q.data
  if (!d) return null

  return (
    <Card className="flex flex-col gap-4 p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold">{t('onboarding.sevenDays')}</h2>
        <div className="flex items-center gap-2">
          {d.decision.value && <Badge tone={d.decision.value === 'fit' ? 'success' : 'danger'}>{t(`onboarding.decision.${d.decision.value}`)}</Badge>}
          {d.can.package && (
            <Button variant="outline" className="h-8" disabled={pkg.isPending} onClick={() => pkg.mutate()}>
              {t('onboarding.sendPackage')}
            </Button>
          )}
        </div>
      </div>
      <ol className="flex flex-col gap-3">
        {d.days.map((day) => (
          <DayRow key={day.day_no} day={day} base={base} canReport={d.can.report} canFeedback={d.can.feedback} onSaved={refresh} />
        ))}
      </ol>
      {d.decision.note && <p className="text-sm text-muted">{d.decision.note}</p>}
      {d.can.decide && (
        <div className="flex flex-col gap-2 border-t border-border pt-4">
          <p className="text-sm font-medium">{t('onboarding.dayDecision')}</p>
          <p className="text-xs text-muted">{t('onboarding.dayDecisionHint')}</p>
          <Input value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} placeholder={t('answers.decision.note')} aria-label={t('answers.decision.note')} />
          <div className="flex gap-2">
            <Button disabled={decide.isPending} onClick={() => decide.mutate('fit')}>
              {t('onboarding.decision.fit')}
            </Button>
            <Button variant="outline" className="text-danger" disabled={decide.isPending || !note.trim()} onClick={() => decide.mutate('not_fit')}>
              {t('onboarding.decision.not_fit')}
            </Button>
          </div>
          {decide.isError && <p role="alert" className="text-sm text-danger">{errorText(t, decide.error)}</p>}
        </div>
      )}
      {d.decision.next_enrollment_id && (
        <a href={`/internship/enrollments/${d.decision.next_enrollment_id}`} className="text-sm font-medium text-primary hover:underline">
          {t('onboarding.openOnboarding')}
        </a>
      )}
    </Card>
  )
}

function DayRow({ day, base, canReport, canFeedback, onSaved }: { day: Day; base: string; canReport: boolean; canFeedback: boolean; onSaved: () => void }) {
  const { t, i18n } = useTranslation()
  const [seen, setSeen] = useState(day.seen ?? '')
  const [understood, setUnderstood] = useState(day.understood ?? '')
  const [done, setDone] = useState(day.done ?? '')
  const [fb, setFb] = useState('')
  const [open, setOpen] = useState(false)
  const save = useMutation({ mutationFn: () => send('PUT', `${base}/daily/${day.day_no}`, { seen, understood, done }), onSuccess: () => (setOpen(false), onSaved()) })
  const feedback = useMutation({ mutationFn: () => send('POST', `${base}/daily/${day.day_no}/feedback`, { text: fb }), onSuccess: () => (setFb(''), onSaved()) })
  const filled = !!(day.seen || day.understood || day.done)
  return (
    <li className={'rounded-control border border-border p-3 text-sm ' + (day.open ? '' : 'opacity-50')}>
      <div className="flex items-center justify-between">
        <span className="font-medium">{t('onboarding.day', { n: day.day_no })}</span>
        <Badge tone={filled ? 'success' : 'neutral'}>{filled ? t('onboarding.reported') : t('onboarding.noReport')}</Badge>
      </div>
      {filled && !open && (
        <dl className="mt-2 grid gap-1 text-muted">
          {day.seen && <div><span className="text-text">{t('onboarding.seen')}:</span> {day.seen}</div>}
          {day.understood && <div><span className="text-text">{t('onboarding.understood')}:</span> {day.understood}</div>}
          {day.done && <div><span className="text-text">{t('onboarding.done')}:</span> {day.done}</div>}
        </dl>
      )}
      {day.feedback.map((f) => (
        <p key={f.id} className="mt-1 text-xs text-muted">
          <Badge>{t(`onboarding.role.${f.role}`)}</Badge> {f.author}: {f.text} · {formatDateTime(f.created_at, i18n.language)}
        </p>
      ))}
      {canReport && day.open && !open && (
        <Button variant="outline" className="mt-2 h-8" onClick={() => setOpen(true)}>
          {filled ? t('coordReport.edit') : t('onboarding.writeReport')}
        </Button>
      )}
      {open && (
        <div className="mt-2 flex flex-col gap-2">
          {([['seen', seen, setSeen], ['understood', understood, setUnderstood], ['done', done, setDone]] as const).map(([k, v, set]) => (
            <label key={k} className="flex flex-col gap-1 text-xs text-muted">
              {t(`onboarding.${k}`)}
              <textarea value={v} onChange={(e) => set(e.target.value)} rows={2} maxLength={2000} className={area} />
            </label>
          ))}
          {save.isError && <p role="alert" className="text-sm text-danger">{errorText(t, save.error)}</p>}
          <div className="flex gap-2">
            <Button disabled={save.isPending} onClick={() => save.mutate()}>
              {t('common.save')}
            </Button>
            <Button variant="outline" onClick={() => setOpen(false)}>
              {t('common.cancel')}
            </Button>
          </div>
        </div>
      )}
      {canFeedback && day.open && (
        <div className="mt-2 flex gap-2">
          <Input value={fb} onChange={(e) => setFb(e.target.value)} maxLength={2000} placeholder={t('onboarding.feedbackPlaceholder')} aria-label={t('onboarding.feedbackPlaceholder')} />
          <Button variant="outline" disabled={fb.trim().length < 2 || feedback.isPending} onClick={() => feedback.mutate()}>
            {t('tasks.send')}
          </Button>
        </div>
      )}
    </li>
  )
}
