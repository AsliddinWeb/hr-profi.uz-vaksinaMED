import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'

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
import { EmployeePicker, type Picked } from '../retention/EmployeePicker'

export interface Rotation {
  id: number
  status: 'pending' | 'approved' | 'active' | 'completed' | 'rejected' | 'cancelled'
  employee: { id: number; name: string } | null
  from_branch: { id: number; name: string | null }
  to_branch: { id: number; name: string | null }
  start_date: string
  end_date: string
  reason: string
  requested_by: string | null
  decided_by: string | null
  decided_at: string | null
  decision_note: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string
}

const TONE = { pending: 'warning', approved: 'info', active: 'success', completed: 'neutral', rejected: 'danger', cancelled: 'neutral' } as const
const area = 'w-full rounded-control border border-border bg-surface px-3 py-2 text-sm'
const FILTERS = ['open', 'pending', 'active', 'completed'] as const

/** /org/rotations: filialdan filialga vaqtincha o'tkazishlar. */
export function RotationsPage() {
  const { t, i18n } = useTranslation()
  const can = useCan()
  const [status, setStatus] = useState<string>('open')
  const list = useQuery({ queryKey: ['rotations', status], queryFn: () => api<Rotation[]>(`/api/v1/rotations?status=${status}`), refetchInterval: 60_000 })
  const pill = (on: boolean) => 'rounded-full border px-3 py-1.5 text-xs font-medium ' + (on ? 'border-primary bg-primary text-primary-fg' : 'border-border bg-surface text-muted hover:text-text')
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title={t('rotation.title')}
        subtitle={t('rotation.subtitle')}
        actions={
          (can('rotations.manage') || can('rotations.request')) && (
            <Link to="/org/rotations/new">
              <Button>
                <Plus className="size-4" />
                {t('rotation.add')}
              </Button>
            </Link>
          )
        }
      />
      <div className="flex flex-wrap gap-2">
        {FILTERS.map((s) => (
          <button key={s} aria-pressed={status === s} onClick={() => setStatus(s)} className={pill(status === s)}>
            {t(`rotation.filter.${s}`)}
          </button>
        ))}
      </div>
      {!list.data ? (
        <Skeleton className="h-40" />
      ) : (
        <div className="flex flex-col gap-3">
          {list.data.map((r) => (
            <Link key={r.id} to={`/org/rotations/${r.id}`}>
              <Card className="flex flex-wrap items-center justify-between gap-3 p-4 hover:bg-surface-2">
                <div>
                  <div className="font-medium">{r.employee?.name}</div>
                  <div className="text-sm text-muted">
                    {r.from_branch.name} → {r.to_branch.name} · {formatDate(r.start_date, i18n.language)} – {formatDate(r.end_date, i18n.language)}
                  </div>
                </div>
                <Badge tone={TONE[r.status]}>{t(`rotation.status.${r.status}`)}</Badge>
              </Card>
            </Link>
          ))}
          {list.data.length === 0 && <Card className="p-8 text-center text-muted">{t('common.empty')}</Card>}
        </div>
      )}
    </div>
  )
}

/** /org/rotations/new: yangi rotatsiya (`?employee=ID` xodim kartochkasidan keladi). */
export function RotationFormPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const can = useCan()
  const [params] = useSearchParams()
  const preset = Number(params.get('employee')) || null
  const presetEmp = useQuery({ queryKey: ['employee', preset], queryFn: () => api<{ id: number; full_name: string; branch: { id: number } | null }>(`/api/v1/employees/${preset}`), enabled: !!preset })
  const [picked, setPicked] = useState<Picked | null>(null)
  const emp: Picked | null = picked ?? (presetEmp.data ? { id: presetEmp.data.id, name: presetEmp.data.full_name } : null)
  const branches = useQuery({ queryKey: ['branches', 'all'], queryFn: () => api<{ id: number; number: number | null; name: string }[]>('/api/v1/rotations/branches') })
  const [to, setTo] = useState('')
  const [start, setStart] = useState(todayLocal())
  const [end, setEnd] = useState('')
  const [reason, setReason] = useState('')
  const save = useMutation({
    mutationFn: () => send<Rotation>('POST', '/api/v1/rotations', { employee_id: emp?.id, to_branch_id: Number(to), start_date: start, end_date: end, reason }),
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['rotations'] })
      toast.push({ title: t(r.status === 'pending' ? 'rotation.requested' : 'rotation.created'), tone: 'success' })
      navigate(`/org/rotations/${r.id}`, { replace: true })
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={t('rotation.add')} subtitle={t(can('rotations.manage') ? 'rotation.hintHr' : 'rotation.hintLead')} backTo="/org/rotations" backLabel={t('rotation.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('rotation.who')}>
          <EmployeePicker value={emp} onChange={setPicked} />
        </FormSection>
        <FormSection title={t('rotation.where')}>
          <Field label={t('rotation.toBranch')}>
            {(id) => (
              <Select id={id} value={to} onChange={(e) => setTo(e.target.value)}>
                <option value="">—</option>
                {branches.data?.filter((b) => b.id !== presetEmp.data?.branch?.id).map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.number ? `${b.number} · ` : ''}
                    {b.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('rotation.start')}>{(id) => <Input id={id} type="date" value={start} min={todayLocal()} onChange={(e) => setStart(e.target.value)} />}</Field>
            <Field label={t('rotation.end')}>{(id) => <Input id={id} type="date" value={end} min={start} onChange={(e) => setEnd(e.target.value)} />}</Field>
          </div>
          <Field label={t('rotation.reason')}>{(id) => <textarea id={id} value={reason} onChange={(e) => setReason(e.target.value)} rows={3} maxLength={300} className={area} />}</Field>
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate('/org/rotations')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !emp || !to || !end || reason.trim().length < 3}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}

/** /org/rotations/:id: tafsilot, tasdiqlash/rad etish va bekor qilish. */
export function RotationDetailPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const qc = useQueryClient()
  const can = useCan()
  const q = useQuery({ queryKey: ['rotations', 'one', id], queryFn: () => api<Rotation>(`/api/v1/rotations/${id}`), retry: false })
  const [note, setNote] = useState('')
  const act = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: unknown }) => send<Rotation>('POST', `/api/v1/rotations/${id}/${path}`, body),
    onSuccess: () => {
      setNote('')
      void qc.invalidateQueries({ queryKey: ['rotations'] })
    },
  })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!q.data) return <Skeleton className="mx-auto h-64 max-w-3xl" />
  const r = q.data
  const manage = can('rotations.manage')
  const row = (label: string, value: string | null | undefined) => value && (
    <div className="flex justify-between gap-4 text-sm">
      <span className="text-muted">{label}</span>
      <span className="text-right font-medium">{value}</span>
    </div>
  )
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <PageHeader title={r.employee?.name ?? ''} subtitle={`${r.from_branch.name} → ${r.to_branch.name}`} backTo="/org/rotations" backLabel={t('rotation.title')} actions={<Badge tone={TONE[r.status]}>{t(`rotation.status.${r.status}`)}</Badge>} />
      <Card className="flex flex-col gap-2 p-5">
        {row(t('rotation.period'), `${formatDate(r.start_date, i18n.language)} – ${formatDate(r.end_date, i18n.language)}`)}
        {row(t('rotation.reason'), r.reason)}
        {row(t('rotation.requestedBy'), r.requested_by)}
        {row(t('rotation.decidedBy'), r.decided_by && `${r.decided_by}${r.decided_at ? ' · ' + formatDateTime(r.decided_at, i18n.language) : ''}`)}
        {row(t('rotation.decisionNote'), r.decision_note)}
        {row(t('rotation.startedAt'), r.started_at && formatDateTime(r.started_at, i18n.language))}
        {row(t('rotation.finishedAt'), r.finished_at && formatDateTime(r.finished_at, i18n.language))}
      </Card>
      {act.isError && <p role="alert" className="text-sm text-danger">{errorText(t, act.error)}</p>}
      {r.status === 'pending' && manage && (
        <Card className="flex flex-col gap-3 p-5">
          <Field label={t('rotation.decisionNote')}>{(fid) => <textarea id={fid} value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={500} className={area} />}</Field>
          <div className="flex gap-2">
            <Button disabled={act.isPending} onClick={() => act.mutate({ path: 'decide', body: { action: 'approve', note: note || null } })}>
              {t('rotation.approve')}
            </Button>
            <Button variant="outline" disabled={act.isPending} onClick={() => act.mutate({ path: 'decide', body: { action: 'reject', note: note || null } })}>
              {t('rotation.reject')}
            </Button>
          </div>
        </Card>
      )}
      {['pending', 'approved', 'active'].includes(r.status) && (
        <div>
          <Button variant="outline" disabled={act.isPending} onClick={() => act.mutate({ path: 'cancel' })}>
            {t(r.status === 'active' ? 'rotation.endNow' : 'rotation.cancel')}
          </Button>
        </div>
      )}
    </div>
  )
}
