import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { formatDate, formatDateTime } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { todayLocal } from '../attendance/api'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import { EmployeePicker, type Picked } from './EmployeePicker'

export interface Case {
  id: number
  status: 'open' | 'retained' | 'leaving'
  risk_level: 'low' | 'medium' | 'high'
  source: 'manual' | 'auto' | 'notice'
  employee: { id: number; name: string }
  branch: string | null
  note: string | null
  notice_date: string | null
  planned_leave_date: string | null
  reported_by: string | null
  created_at: string
  hr: { note: string | null; by: string | null; at: string | null }
  trainer: { note: string | null; by: string | null; at: string | null }
  auditor: { note: string | null; by: string | null; at: string | null }
  decision: 'stay' | 'leave' | null
  decision_note: string | null
  last_discussed_on: string | null
  events: { action: string; actor: string | null; text: string | null; at: string }[]
  can?: { interview: boolean; trainer: boolean; audit: boolean; decide: boolean }
  offboarding_id?: number | null
}
const RISK_TONE = { low: 'neutral', medium: 'warning', high: 'danger' } as const
const STATUS_TONE = { open: 'warning', retained: 'success', leaving: 'danger' } as const
const area = 'w-full rounded-control border border-border bg-surface px-3 py-2 text-sm'

/** /retention: ketish xavfi holatlari va haftalik uchrashuv. */
export function RetentionPage() {
  const { t, i18n } = useTranslation()
  const can = useCan()
  const [status, setStatus] = useState('open')
  const list = useQuery({ queryKey: ['retention', 'cases', status], queryFn: () => api<Case[]>(`/api/v1/retention/cases?status=${status}`), refetchInterval: 60_000 })
  const meetings = useQuery({ queryKey: ['retention', 'meetings'], queryFn: () => api<{ id: number; held_on: string; summary: string; cases: number }[]>('/api/v1/retention/meetings'), enabled: can('retention.manage') || can('retention.read') || can('retention.audit'), retry: false })
  const pill = (on: boolean) => 'rounded-full border px-3 py-1.5 text-xs font-medium ' + (on ? 'border-primary bg-primary text-primary-fg' : 'border-border bg-surface text-muted hover:text-text')
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title={t('retention.title')}
        subtitle={t('retention.subtitle')}
        actions={
          <div className="flex gap-2">
            {can('retention.manage') && (
              <Link to="/retention/meetings/new">
                <Button variant="outline">{t('retention.meeting.add')}</Button>
              </Link>
            )}
            {(can('retention.report') || can('retention.manage')) && (
              <Link to="/retention/new">
                <Button>
                  <Plus className="size-4" />
                  {t('retention.report')}
                </Button>
              </Link>
            )}
          </div>
        }
      />
      <div className="flex gap-2">
        {['open', 'retained', 'leaving'].map((s) => (
          <button key={s} aria-pressed={status === s} onClick={() => setStatus(s)} className={pill(status === s)}>
            {t(`retention.status.${s}`)}
          </button>
        ))}
      </div>
      {!list.data ? (
        <Skeleton className="h-40" />
      ) : (
        <div className="flex flex-col gap-3">
          {list.data.map((c) => (
            <Link key={c.id} to={`/retention/${c.id}`}>
              <Card className="flex flex-wrap items-center justify-between gap-3 p-4 hover:bg-surface-2">
                <div>
                  <div className="font-medium">{c.employee.name}</div>
                  <div className="text-sm text-muted">{[c.branch, c.note].filter(Boolean).join(' · ')}</div>
                </div>
                <div className="flex gap-2">
                  {c.source !== 'manual' && <Badge>{t(`retention.source.${c.source}`)}</Badge>}
                  <Badge tone={RISK_TONE[c.risk_level]}>{t(`retention.risk.${c.risk_level}`)}</Badge>
                  <Badge tone={STATUS_TONE[c.status]}>{t(`retention.status.${c.status}`)}</Badge>
                </div>
              </Card>
            </Link>
          ))}
          {list.data.length === 0 && <Card className="p-8 text-center text-muted">{t('common.empty')}</Card>}
        </div>
      )}
      {meetings.data && meetings.data.length > 0 && (
        <Card className="flex flex-col gap-2 p-5">
          <h2 className="font-semibold">{t('retention.meeting.title')}</h2>
          {meetings.data.slice(0, 5).map((m) => (
            <p key={m.id} className="text-sm">
              <span className="text-muted">{formatDate(m.held_on, i18n.language)} · {m.cases}</span> {m.summary}
            </p>
          ))}
        </Card>
      )}
    </div>
  )
}

/** /retention/new: ketish xavfini bildirish. */
export function RetentionFormPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [emp, setEmp] = useState<Picked | null>(null)
  const [risk, setRisk] = useState('medium')
  const [note, setNote] = useState('')
  const [notice, setNotice] = useState('')
  const [leave, setLeave] = useState('')
  const save = useMutation({
    mutationFn: () => send<Case>('POST', '/api/v1/retention/cases', { employee_id: emp?.id, risk_level: risk, note, notice_date: notice || null, planned_leave_date: leave || null }),
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['retention'] })
      toast.push({ title: t('retention.reported'), tone: 'success' })
      navigate(`/retention/${r.id}`, { replace: true })
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={t('retention.report')} subtitle={t('retention.reportHint')} backTo="/retention" backLabel={t('retention.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('growth.career.who')}>
          <EmployeePicker value={emp} onChange={setEmp} />
          <Field label={t('retention.riskLabel')}>
            {(id) => (
              <Select id={id} value={risk} onChange={(e) => setRisk(e.target.value)}>
                {['low', 'medium', 'high'].map((r) => (
                  <option key={r} value={r}>
                    {t(`retention.risk.${r}`)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label={t('retention.why')}>{(id) => <textarea id={id} value={note} onChange={(e) => setNote(e.target.value)} rows={4} maxLength={2000} className={area} />}</Field>
        </FormSection>
        <FormSection title={t('retention.noticeTitle')} description={t('retention.noticeHint')}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('retention.noticeDate')}>{(id) => <Input id={id} type="date" value={notice} max={todayLocal()} onChange={(e) => setNotice(e.target.value)} />}</Field>
            <Field label={t('retention.leaveDate')}>{(id) => <Input id={id} type="date" value={leave} onChange={(e) => setLeave(e.target.value)} />}</Field>
          </div>
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate('/retention')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !emp || note.trim().length < 3}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}

/** /retention/:id: HR suhbati, trener yechimi, auditor xulosasi va qaror. */
export function RetentionDetailPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const qc = useQueryClient()
  const navigate = useNavigate()
  const q = useQuery({ queryKey: ['retention', 'case', id], queryFn: () => api<Case>(`/api/v1/retention/cases/${id}`), retry: false })
  const [text, setText] = useState<Record<string, string>>({})
  const act = useMutation({
    mutationFn: ({ path, body }: { path: string; body: unknown }) => send<Case>('POST', `/api/v1/retention/cases/${id}/${path}`, body),
    onSuccess: (r) => {
      setText({})
      void qc.invalidateQueries({ queryKey: ['retention'] })
      if (r.offboarding_id) navigate(`/offboarding/${r.offboarding_id}`)
    },
  })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const c = q.data
  if (!c) return <Skeleton className="mx-auto h-72 max-w-3xl" />
  const sections = [
    { key: 'hr', path: 'interview', data: c.hr, can: c.can?.interview },
    { key: 'trainer', path: 'trainer', data: c.trainer, can: c.can?.trainer },
    { key: 'auditor', path: 'audit', data: c.auditor, can: c.can?.audit },
  ] as const
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <PageHeader title={c.employee.name} subtitle={c.branch ?? ''} backTo="/retention" backLabel={t('retention.title')} actions={<Badge tone={STATUS_TONE[c.status]}>{t(`retention.status.${c.status}`)}</Badge>} />
      <Card className="flex flex-col gap-2 p-5 text-sm">
        <div className="flex flex-wrap gap-2">
          <Badge tone={RISK_TONE[c.risk_level]}>{t(`retention.risk.${c.risk_level}`)}</Badge>
          {c.source !== 'manual' && <Badge>{t(`retention.source.${c.source}`)}</Badge>}
        </div>
        <p>{c.note}</p>
        <p className="text-xs text-muted">
          {c.reported_by} · {formatDateTime(c.created_at, i18n.language)}
          {c.notice_date && ` · ${t('retention.noticeDate')}: ${formatDate(c.notice_date, i18n.language)}`}
          {c.planned_leave_date && ` · ${t('retention.leaveDate')}: ${formatDate(c.planned_leave_date, i18n.language)}`}
        </p>
      </Card>
      {sections.map((s) => (
        <Card key={s.key} className="flex flex-col gap-2 p-5">
          <h2 className="font-semibold">{t(`retention.step.${s.key}`)}</h2>
          {s.data.note && (
            <p className="text-sm">
              {s.data.note} <span className="text-xs text-muted">· {s.data.by} · {formatDateTime(s.data.at, i18n.language)}</span>
            </p>
          )}
          {s.can && (
            <div className="flex flex-col gap-2">
              <textarea value={text[s.key] ?? ''} onChange={(e) => setText({ ...text, [s.key]: e.target.value })} rows={2} maxLength={3000} className={area} aria-label={t(`retention.step.${s.key}`)} />
              <div>
                <Button variant="outline" disabled={act.isPending || (text[s.key] ?? '').trim().length < 3} onClick={() => act.mutate({ path: s.path, body: { note: text[s.key] } })}>
                  {t('common.save')}
                </Button>
              </div>
            </div>
          )}
        </Card>
      ))}
      {c.can?.decide && (
        <Card className="flex flex-col gap-3 p-5">
          <h2 className="font-semibold">{t('retention.decideTitle')}</h2>
          <p className="text-xs text-muted">{t('retention.decideHint')}</p>
          <Input value={text.decision ?? ''} onChange={(e) => setText({ ...text, decision: e.target.value })} maxLength={2000} placeholder={t('answers.decision.note')} aria-label={t('answers.decision.note')} />
          <div className="flex gap-2">
            <Button disabled={act.isPending} onClick={() => act.mutate({ path: 'decide', body: { decision: 'stay', note: text.decision || null } })}>
              {t('retention.stay')}
            </Button>
            <Button variant="outline" className="text-danger" disabled={act.isPending} onClick={() => act.mutate({ path: 'decide', body: { decision: 'leave', note: text.decision || null } })}>
              {t('retention.leave')}
            </Button>
          </div>
        </Card>
      )}
      {c.decision && (
        <p className="text-sm">
          <Badge tone={c.decision === 'stay' ? 'success' : 'danger'}>{t(`retention.${c.decision}`)}</Badge> {c.decision_note}
        </p>
      )}
      {act.isError && <p role="alert" className="text-sm text-danger">{errorText(t, act.error)}</p>}
      <Card className="p-5">
        <h2 className="font-semibold">{t('answers.history')}</h2>
        <ol className="mt-3 flex flex-col gap-3 border-l border-border pl-5">
          {c.events.map((e, i) => (
            <li key={i} className="relative text-sm">
              <span className="absolute -left-[26px] top-1.5 size-2.5 rounded-full bg-primary" aria-hidden />
              <div className="flex flex-wrap justify-between gap-2">
                <span className="font-medium">{t(`retention.event.${e.action}`, { defaultValue: e.action })}</span>
                <span className="text-xs text-muted">{formatDateTime(e.at, i18n.language)}</span>
              </div>
              {e.actor && <div className="text-xs text-muted">{e.actor}</div>}
              {e.text && <p className="mt-1 text-muted">{e.text}</p>}
            </li>
          ))}
        </ol>
      </Card>
    </div>
  )
}

/** /retention/meetings/new: haftalik uchrashuv xulosasi. */
export function MeetingFormPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [date, setDate] = useState(todayLocal)
  const [summary, setSummary] = useState('')
  const [picked, setPicked] = useState<number[]>([])
  const open = useQuery({ queryKey: ['retention', 'cases', 'open'], queryFn: () => api<Case[]>('/api/v1/retention/cases?status=open') })
  const save = useMutation({
    mutationFn: () => send('POST', '/api/v1/retention/meetings', { held_on: date, summary, case_ids: picked }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['retention'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate('/retention', { replace: true })
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={t('retention.meeting.add')} subtitle={t('retention.meeting.hint')} backTo="/retention" backLabel={t('retention.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('retention.meeting.title')}>
          <Field label={t('attendance.date')}>{(id) => <Input id={id} type="date" value={date} max={todayLocal()} onChange={(e) => setDate(e.target.value)} required className="max-w-52" />}</Field>
          <Field label={t('retention.meeting.summary')}>{(id) => <textarea id={id} value={summary} onChange={(e) => setSummary(e.target.value)} rows={4} maxLength={3000} className={area} />}</Field>
        </FormSection>
        <FormSection title={t('retention.meeting.discussed')}>
          <div className="grid gap-2 sm:grid-cols-2">
            {open.data?.map((c) => (
              <label key={c.id} className="flex items-center gap-2 rounded-control border border-border px-3 py-2 text-sm">
                <input type="checkbox" className="size-4" checked={picked.includes(c.id)} onChange={() => setPicked((p) => (p.includes(c.id) ? p.filter((x) => x !== c.id) : [...p, c.id]))} />
                {c.employee.name}
              </label>
            ))}
            {open.data?.length === 0 && <p className="text-sm text-muted">{t('common.empty')}</p>}
          </div>
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate('/retention')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || summary.trim().length < 3}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
