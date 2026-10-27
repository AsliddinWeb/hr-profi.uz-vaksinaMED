import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2 } from 'lucide-react'
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
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { fromLocalInput } from '../attendance/api'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import type { Enrollment, Page } from './api'

interface ClassRow {
  id: number
  title: string
  kind: 'lesson' | 'practice'
  starts_at: string
  place: string | null
  trainer: { id: number; name: string | null } | null
  attendance_marked_at: string | null
  count: number
  present: number
  attendees: { employee_id: number; name: string; present: boolean | null }[]
  can_mark?: boolean
}

/** /internship/classes: oflayn dars va amaliyotlar jadvali. */
export function ClassesPage() {
  const { t, i18n } = useTranslation()
  const manage = useCan()('internship.manage')
  const [scope, setScope] = useState<'upcoming' | 'past'>('upcoming')
  const q = useQuery({ queryKey: ['internship', 'classes', scope], queryFn: () => api<ClassRow[]>(`/api/v1/internship/classes?scope=${scope}`), refetchInterval: 60_000 })
  const pill = (on: boolean) => 'rounded-full border px-3 py-1.5 text-xs font-medium ' + (on ? 'border-primary bg-primary text-primary-fg' : 'border-border bg-surface text-muted hover:text-text')
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title={t('onboarding.classes.title')}
        subtitle={t('onboarding.classes.subtitle')}
        actions={
          manage && (
            <Link to="/internship/classes/new">
              <Button>
                <Plus className="size-4" />
                {t('onboarding.classes.add')}
              </Button>
            </Link>
          )
        }
      />
      <div className="flex gap-2">
        {(['upcoming', 'past'] as const).map((s) => (
          <button key={s} aria-pressed={scope === s} onClick={() => setScope(s)} className={pill(scope === s)}>
            {t(`onboarding.classes.${s}`)}
          </button>
        ))}
      </div>
      {!q.data ? (
        <Skeleton className="h-40" />
      ) : (
        <div className="flex flex-col gap-3">
          {q.data.map((c) => (
            <Link key={c.id} to={`/internship/classes/${c.id}`}>
              <Card className="flex flex-wrap items-center justify-between gap-3 p-4 hover:bg-surface-2">
                <div>
                  <div className="font-medium">{c.title}</div>
                  <div className="text-sm text-muted">
                    {formatDateTime(c.starts_at, i18n.language)} · {c.place ?? '—'} · {c.trainer?.name ?? '—'}
                  </div>
                </div>
                <div className="flex gap-2">
                  <Badge>{t(`onboarding.classes.kind.${c.kind}`)}</Badge>
                  <Badge tone={c.attendance_marked_at ? 'success' : 'neutral'}>{c.attendance_marked_at ? `${c.present}/${c.count}` : `${c.count}`}</Badge>
                </div>
              </Card>
            </Link>
          ))}
          {q.data.length === 0 && <Card className="p-8 text-center text-muted">{t('common.empty')}</Card>}
        </div>
      )}
    </div>
  )
}

/** /internship/classes/new */
export function ClassFormPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [title, setTitle] = useState('')
  const [kind, setKind] = useState('lesson')
  const [when, setWhen] = useState('')
  const [place, setPlace] = useState('')
  const [trainer, setTrainer] = useState('')
  const [picked, setPicked] = useState<number[]>([])
  const interns = useQuery({ queryKey: ['internship', 'active-interns'], queryFn: () => api<Page<Enrollment>>('/api/v1/internship/enrollments?status=active&size=100') })
  const mentors = useQuery({ queryKey: ['internship', 'mentors'], queryFn: () => api<{ id: number; name: string }[]>('/api/v1/internship/mentors') })
  const save = useMutation({
    mutationFn: () => send<{ id: number }>('POST', '/api/v1/internship/classes', { title, kind, starts_at: fromLocalInput(when), place: place || null, trainer_id: trainer ? Number(trainer) : null, employee_ids: picked }),
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['internship'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(`/internship/classes/${r.id}`, { replace: true })
    },
  })
  const unique = new Map((interns.data?.items ?? []).map((e) => [e.employee.id, e.employee.name ?? '—']))
  const toggle = (id: number) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]))
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={t('onboarding.classes.add')} backTo="/internship/classes" backLabel={t('onboarding.classes.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('onboarding.classes.what')}>
          <Field label={t('onboarding.classes.name')}>{(id) => <Input id={id} value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={200} />}</Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('onboarding.classes.type')}>
              {(id) => (
                <Select id={id} value={kind} onChange={(e) => setKind(e.target.value)}>
                  {['lesson', 'practice'].map((k) => (
                    <option key={k} value={k}>
                      {t(`onboarding.classes.kind.${k}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('onboarding.classes.when')}>{(id) => <Input id={id} type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} required />}</Field>
            <Field label={t('onboarding.classes.place')}>{(id) => <Input id={id} value={place} onChange={(e) => setPlace(e.target.value)} maxLength={200} />}</Field>
            <Field label={t('onboarding.classes.trainer')}>
              {(id) => (
                <Select id={id} value={trainer} onChange={(e) => setTrainer(e.target.value)}>
                  <option value="">—</option>
                  {mentors.data?.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
        </FormSection>
        <FormSection title={t('onboarding.classes.group')} description={t('onboarding.classes.groupHint')}>
          <div className="grid gap-2 sm:grid-cols-2">
            {[...unique.entries()].map(([id, name]) => (
              <label key={id} className="flex items-center gap-2 rounded-control border border-border px-3 py-2 text-sm">
                <input type="checkbox" className="size-4" checked={picked.includes(id)} onChange={() => toggle(id)} />
                {name}
              </label>
            ))}
            {unique.size === 0 && <p className="text-sm text-muted">{t('common.empty')}</p>}
          </div>
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate('/internship/classes')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !title.trim() || !when || picked.length === 0}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}

/** /internship/classes/:id: qatnashuvni belgilash. */
export function ClassDetailPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const manage = useCan()('internship.manage')
  const q = useQuery({ queryKey: ['internship', 'class', id], queryFn: () => api<ClassRow>(`/api/v1/internship/classes/${id}`), retry: false })
  const [marks, setMarks] = useState<Record<number, boolean>>({})
  const mark = useMutation({
    mutationFn: () => send<{ absent: number }>('POST', `/api/v1/internship/classes/${id}/attendance`, { marks: (q.data?.attendees ?? []).map((a) => ({ employee_id: a.employee_id, present: marks[a.employee_id] ?? a.present ?? false })) }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['internship'] })
      toast.push({ title: t('onboarding.classes.marked'), tone: 'success' })
    },
  })
  const remove = useMutation({ mutationFn: () => send('DELETE', `/api/v1/internship/classes/${id}`), onSuccess: () => (void qc.invalidateQueries({ queryKey: ['internship'] }), navigate('/internship/classes', { replace: true })) })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const c = q.data
  if (!c) return <Skeleton className="mx-auto h-72 max-w-3xl" />
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <PageHeader title={c.title} subtitle={`${formatDateTime(c.starts_at, i18n.language)} · ${c.place ?? '—'}`} backTo="/internship/classes" backLabel={t('onboarding.classes.title')} />
      <Card className="flex flex-col gap-3 p-5">
        <p className="text-sm text-muted">{t('onboarding.classes.trainer')}: {c.trainer?.name ?? '—'}</p>
        <ul className="divide-y divide-border text-sm">
          {c.attendees.map((a) => {
            const v = marks[a.employee_id] ?? a.present
            return (
              <li key={a.employee_id} className="flex items-center justify-between gap-3 py-2">
                <span>{a.name}</span>
                {c.can_mark ? (
                  <div className="flex gap-2" role="group" aria-label={a.name}>
                    <Button variant={v === true ? 'primary' : 'outline'} className="h-8" onClick={() => setMarks({ ...marks, [a.employee_id]: true })}>
                      {t('onboarding.classes.came')}
                    </Button>
                    <Button variant={v === false ? 'primary' : 'outline'} className="h-8" onClick={() => setMarks({ ...marks, [a.employee_id]: false })}>
                      {t('onboarding.classes.absent')}
                    </Button>
                  </div>
                ) : (
                  <Badge tone={a.present === null ? 'neutral' : a.present ? 'success' : 'danger'}>{a.present === null ? '—' : a.present ? t('onboarding.classes.came') : t('onboarding.classes.absent')}</Badge>
                )}
              </li>
            )
          })}
        </ul>
        {c.can_mark && (
          <div className="flex gap-2">
            <Button disabled={mark.isPending} onClick={() => mark.mutate()}>
              {t('onboarding.classes.saveAttendance')}
            </Button>
            {manage && (
              <Button
                variant="outline"
                className="text-danger"
                onClick={async () => {
                  if (await confirm({ title: t('common.delete'), body: c.title, danger: true, confirmLabel: t('common.delete') })) remove.mutate()
                }}
              >
                <Trash2 className="size-4" />
                {t('common.delete')}
              </Button>
            )}
          </div>
        )}
        {mark.isError && <p role="alert" className="text-sm text-danger">{errorText(t, mark.error)}</p>}
      </Card>
    </div>
  )
}
