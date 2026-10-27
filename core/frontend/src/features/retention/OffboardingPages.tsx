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
import { addDays, fromLocalInput, todayLocal } from '../attendance/api'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import { EmployeePicker, type Picked } from './EmployeePicker'

const REASONS = ['salary', 'manager', 'workload', 'team', 'growth', 'personal', 'offer', 'fired', 'other'] as const
const RISKS = ['shortage', 'access', 'understaff', 'others_leaving', 'competitor'] as const
const area = 'w-full rounded-control border border-border bg-surface px-3 py-2 text-sm'

interface Off {
  id: number
  status: 'open' | 'completed' | 'cancelled'
  employee: { id: number; name: string }
  leave_date: string | null
  reason_type: string | null
  reason_text: string | null
  prevent_text: string | null
  risks: string[]
  exit_at: string | null
  exit_by: string | null
  approved_at: string | null
  approved_by: string | null
  completed_at: string | null
  access_closed: boolean
  measures: { task_id: number; title: string; assignee: string | null; due: string | null; status: string | null }[]
  can?: { exit: boolean; approve: boolean; complete: boolean }
}
interface Analytics {
  total: number
  reasons: Record<string, number>
  risks: Record<string, number>
  branches: Record<string, number>
}

/** /offboarding: jarayondagi va yakunlangan ketishlar, ketish sabablari bazasi. */
export function OffboardingPage() {
  const { t, i18n } = useTranslation()
  const can = useCan()
  const [status, setStatus] = useState('open')
  const [from] = useState(() => addDays(todayLocal(), -180))
  const list = useQuery({ queryKey: ['offboarding', status], queryFn: () => api<Off[]>(`/api/v1/offboarding?status=${status}`) })
  const stats = useQuery({ queryKey: ['offboarding', 'analytics'], queryFn: () => api<Analytics>(`/api/v1/offboarding/analytics?start=${from}&end=${todayLocal()}`) })
  const pill = (on: boolean) => 'rounded-full border px-3 py-1.5 text-xs font-medium ' + (on ? 'border-primary bg-primary text-primary-fg' : 'border-border bg-surface text-muted hover:text-text')
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title={t('offboarding.title')}
        subtitle={t('offboarding.subtitle')}
        actions={
          can('retention.manage') && (
            <Link to="/offboarding/new">
              <Button>
                <Plus className="size-4" />
                {t('offboarding.start')}
              </Button>
            </Link>
          )
        }
      />
      {stats.data && stats.data.total > 0 && (
        <Card className="grid gap-4 p-5 text-sm sm:grid-cols-3">
          <Stat title={t('offboarding.reasons')} data={stats.data.reasons} label={(k) => t(`offboarding.reason.${k}`)} />
          <Stat title={t('offboarding.risks')} data={stats.data.risks} label={(k) => t(`offboarding.risk.${k}`)} />
          <Stat title={t('offboarding.branches')} data={stats.data.branches} label={(k) => k} />
        </Card>
      )}
      <div className="flex gap-2">
        {['open', 'completed'].map((s) => (
          <button key={s} aria-pressed={status === s} onClick={() => setStatus(s)} className={pill(status === s)}>
            {t(`offboarding.status.${s}`)}
          </button>
        ))}
      </div>
      {!list.data ? (
        <Skeleton className="h-40" />
      ) : (
        <div className="flex flex-col gap-3">
          {list.data.map((o) => (
            <Link key={o.id} to={`/offboarding/${o.id}`}>
              <Card className="flex flex-wrap items-center justify-between gap-3 p-4 hover:bg-surface-2">
                <div>
                  <div className="font-medium">{o.employee.name}</div>
                  <div className="text-sm text-muted">{o.leave_date ? formatDate(o.leave_date, i18n.language) : '—'}</div>
                </div>
                <div className="flex gap-2">
                  {o.reason_type && <Badge>{t(`offboarding.reason.${o.reason_type}`)}</Badge>}
                  <Badge tone={o.exit_at ? 'success' : 'warning'}>{o.exit_at ? t('offboarding.exitDone') : t('offboarding.exitMissing')}</Badge>
                </div>
              </Card>
            </Link>
          ))}
          {list.data.length === 0 && <Card className="p-8 text-center text-muted">{t('common.empty')}</Card>}
        </div>
      )}
    </div>
  )
}

function Stat({ title, data, label }: { title: string; data: Record<string, number>; label: (k: string) => string }) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-medium text-muted">{title}</h3>
      <ul className="flex flex-col gap-1">
        {Object.entries(data).map(([k, n]) => (
          <li key={k} className="flex justify-between">
            <span>{label(k)}</span>
            <span className="tabular-nums">{n}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** /offboarding/new */
export function OffboardingFormPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [emp, setEmp] = useState<Picked | null>(null)
  const [leave, setLeave] = useState('')
  const save = useMutation({
    mutationFn: () => send<Off>('POST', '/api/v1/offboarding', { employee_id: emp?.id, leave_date: leave || null }),
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['offboarding'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(`/offboarding/${r.id}`, { replace: true })
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={t('offboarding.start')} subtitle={t('offboarding.startHint')} backTo="/offboarding" backLabel={t('offboarding.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('growth.career.who')}>
          <EmployeePicker value={emp} onChange={setEmp} />
          <Field label={t('retention.leaveDate')}>{(id) => <Input id={id} type="date" value={leave} onChange={(e) => setLeave(e.target.value)} className="max-w-52" />}</Field>
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate('/offboarding')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !emp}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}

/** /offboarding/:id: exit-intervyu, choralar (vazifalar), HRD tasdig'i va rasmiylashtirish. */
export function OffboardingDetailPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const qc = useQueryClient()
  const toast = useToast()
  const q = useQuery({ queryKey: ['offboarding', 'one', id], queryFn: () => api<Off>(`/api/v1/offboarding/${id}`), retry: false })
  const assignees = useQuery({ queryKey: ['retention', 'assignees'], queryFn: () => api<{ id: number; name: string }[]>('/api/v1/internship/mentors'), retry: false })
  const [reason, setReason] = useState('')
  const [text, setText] = useState('')
  const [prevent, setPrevent] = useState('')
  const [risks, setRisks] = useState<string[]>([])
  const [m, setM] = useState({ title: '', assignee: '', due: '' })
  const [leave, setLeave] = useState(todayLocal)
  const done = () => void qc.invalidateQueries({ queryKey: ['offboarding'] })
  const act = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: unknown }) => send('POST', `/api/v1/offboarding/${id}/${path}`, body ?? {}),
    onSuccess: (_r, v) => {
      if (v.path === 'measures') setM({ title: '', assignee: '', due: '' })
      if (v.path === 'complete') toast.push({ title: t('offboarding.completedMsg'), tone: 'success' })
      done()
    },
  })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const o = q.data
  if (!o) return <Skeleton className="mx-auto h-72 max-w-3xl" />
  const live = o.status === 'open'
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <PageHeader title={o.employee.name} subtitle={o.leave_date ? formatDate(o.leave_date, i18n.language) : ''} backTo="/offboarding" backLabel={t('offboarding.title')} actions={<Badge tone={live ? 'warning' : 'success'}>{t(`offboarding.status.${o.status}`)}</Badge>} />
      <Card className="flex flex-col gap-3 p-5">
        <h2 className="font-semibold">{t('offboarding.exit')}</h2>
        {o.exit_at && (
          <div className="text-sm">
            <p>
              <Badge>{t(`offboarding.reason.${o.reason_type}`)}</Badge> {o.reason_text}
            </p>
            {o.prevent_text && <p className="mt-1 text-muted">{t('offboarding.prevent')}: {o.prevent_text}</p>}
            {o.risks.length > 0 && <p className="mt-1 flex flex-wrap gap-1">{o.risks.map((r) => <Badge key={r} tone="warning">{t(`offboarding.risk.${r}`)}</Badge>)}</p>}
            <p className="mt-1 text-xs text-muted">{o.exit_by} · {formatDateTime(o.exit_at, i18n.language)}</p>
          </div>
        )}
        {o.can?.exit && (
          <div className="flex flex-col gap-3 border-t border-border pt-3">
            <Select value={reason} onChange={(e) => setReason(e.target.value)} aria-label={t('offboarding.reasonLabel')}>
              <option value="">{t('offboarding.reasonLabel')}</option>
              {REASONS.map((r) => (
                <option key={r} value={r}>
                  {t(`offboarding.reason.${r}`)}
                </option>
              ))}
            </Select>
            <textarea value={text} onChange={(e) => setText(e.target.value)} rows={3} maxLength={3000} placeholder={t('offboarding.reasonText')} aria-label={t('offboarding.reasonText')} className={area} />
            <textarea value={prevent} onChange={(e) => setPrevent(e.target.value)} rows={2} maxLength={3000} placeholder={t('offboarding.prevent')} aria-label={t('offboarding.prevent')} className={area} />
            <div className="flex flex-wrap gap-3 text-sm">
              {RISKS.map((r) => (
                <label key={r} className="flex items-center gap-2">
                  <input type="checkbox" className="size-4" checked={risks.includes(r)} onChange={() => setRisks((p) => (p.includes(r) ? p.filter((x) => x !== r) : [...p, r]))} />
                  {t(`offboarding.risk.${r}`)}
                </label>
              ))}
            </div>
            <div>
              <Button disabled={act.isPending || !reason || text.trim().length < 3} onClick={() => act.mutate({ path: 'exit', body: { reason_type: reason, reason_text: text, prevent_text: prevent || null, risks } })}>
                {t('offboarding.saveExit')}
              </Button>
            </div>
          </div>
        )}
      </Card>
      <Card className="flex flex-col gap-3 p-5">
        <h2 className="font-semibold">{t('offboarding.measures')}</h2>
        <ul className="divide-y divide-border text-sm">
          {o.measures.map((x) => (
            <li key={x.task_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <Link to={`/tasks/${x.task_id}`} className="font-medium hover:underline">
                {x.title}
              </Link>
              <span className="text-xs text-muted">{x.assignee ?? '—'} · {x.due ? formatDateTime(x.due, i18n.language) : '—'}</span>
              <Badge tone={x.status === 'done' ? 'success' : 'warning'}>{x.status ?? '—'}</Badge>
            </li>
          ))}
          {o.measures.length === 0 && <li className="py-2 text-muted">{t('common.empty')}</li>}
        </ul>
        {live && (o.can?.exit || o.can?.complete) && (
          <div className="grid gap-2 sm:grid-cols-4">
            <Input value={m.title} onChange={(e) => setM({ ...m, title: e.target.value })} maxLength={200} placeholder={t('offboarding.measureTitle')} aria-label={t('offboarding.measureTitle')} className="sm:col-span-2" />
            <Select value={m.assignee} onChange={(e) => setM({ ...m, assignee: e.target.value })} aria-label={t('offboarding.assignee')}>
              <option value="">{t('offboarding.assignee')}</option>
              {assignees.data?.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </Select>
            <Input type="datetime-local" value={m.due} onChange={(e) => setM({ ...m, due: e.target.value })} aria-label={t('offboarding.due')} />
            <div className="sm:col-span-4">
              <Button variant="outline" disabled={act.isPending || m.title.trim().length < 3} onClick={() => act.mutate({ path: 'measures', body: { measures: [{ title: m.title, assignee_id: m.assignee ? Number(m.assignee) : null, due_at: m.due ? fromLocalInput(m.due) : null }] } })}>
                {t('offboarding.addMeasure')}
              </Button>
            </div>
          </div>
        )}
      </Card>
      {live && (
        <Card className="flex flex-col gap-3 p-5">
          {o.approved_at ? <p className="text-sm text-success">{t('offboarding.approved', { name: o.approved_by ?? '' })}</p> : o.can?.approve && (
            <div>
              <Button disabled={act.isPending} onClick={() => act.mutate({ path: 'approve' })}>
                {t('offboarding.approve')}
              </Button>
            </div>
          )}
          {o.can?.complete && (
            <div className="flex flex-wrap items-end gap-3 border-t border-border pt-3">
              <Field label={t('offboarding.leaveDateReal')}>{(fid) => <Input id={fid} type="date" value={leave} max={todayLocal()} onChange={(e) => setLeave(e.target.value)} />}</Field>
              <Button variant="outline" className="text-danger" disabled={act.isPending || !o.exit_at} onClick={() => act.mutate({ path: 'complete', body: { leave_date: leave } })}>
                {t('offboarding.complete')}
              </Button>
              {!o.exit_at && <span className="text-xs text-muted">{t('offboarding.exitFirst')}</span>}
            </div>
          )}
        </Card>
      )}
      {act.isError && <p role="alert" className="text-sm text-danger">{errorText(t, act.error)}</p>}
    </div>
  )
}
