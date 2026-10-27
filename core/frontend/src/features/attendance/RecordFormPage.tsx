import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'

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
import { errorText, fieldErrors } from '../auth/errorText'
import type { Shift } from '../schedule/api'
import { fmtMin, fmtTime, fromLocalInput, toLocalInput, type DayInfo, type RecordDetail } from './api'

/** /attendance/records/new?employee=&date= va /attendance/records/:id/edit: qo'lda tuzatish (sabab majburiy, tarixga yoziladi). */
export function RecordFormPage() {
  const { id } = useParams()
  const [params] = useSearchParams()
  const recordId = id ? Number(id) : null
  const employeeId = Number(params.get('employee'))
  const date = params.get('date') ?? ''

  const record = useQuery({ queryKey: ['attendance', 'record', recordId], queryFn: () => api<RecordDetail>(`/api/v1/attendance/records/${recordId}`), enabled: recordId !== null, retry: false })
  const day = useQuery({
    queryKey: ['attendance', 'day', employeeId, date],
    queryFn: () => api<DayInfo>(`/api/v1/attendance/employees/${employeeId}/day?day=${date}`),
    enabled: recordId === null && !!employeeId && !!date,
    retry: false,
  })
  if (recordId !== null) {
    if (record.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
    if (record.error instanceof ApiError && record.error.status === 404) return <NotFound />
    if (!record.data) return null
    return <RecordForm key={record.data.id} rec={record.data} employeeId={record.data.employee_id} name={record.data.employee?.full_name ?? ''} date={record.data.work_date} scheduled={null} />
  }
  if (!employeeId || !date) return <NotFound />
  if (day.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (day.error instanceof ApiError && day.error.status === 404) return <NotFound />
  if (!day.data) return null
  if (day.data.record) return <NotFound />
  return <RecordForm key={`${employeeId}-${date}`} rec={null} employeeId={employeeId} name={day.data.employee.full_name} date={date} scheduled={day.data.scheduled_shift} />
}

function RecordForm({ rec, employeeId, name, date, scheduled }: { rec: RecordDetail | null; employeeId: number; name: string; date: string; scheduled: Shift | null }) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const back = '/attendance/daily'

  const [checkIn, setCheckIn] = useState(toLocalInput(rec?.check_in_at) || (scheduled ? `${date}T${scheduled.start_time}` : `${date}T09:00`))
  const [checkOut, setCheckOut] = useState(toLocalInput(rec?.check_out_at))
  const [shiftId, setShiftId] = useState((rec ? rec.shift_id : scheduled?.id)?.toString() ?? '')
  const [note, setNote] = useState(rec?.note ?? '')
  const [reason, setReason] = useState('')
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const shifts = useQuery({ queryKey: ['schedule', 'shifts'], queryFn: () => api<Shift[]>('/api/v1/schedule/shifts') })

  const done = (msg: string) => {
    void qc.invalidateQueries({ queryKey: ['attendance'] })
    toast.push({ title: msg, tone: 'success' })
    navigate(back)
  }
  const save = useMutation({
    mutationFn: () => {
      const body = { check_in_at: fromLocalInput(checkIn), check_out_at: fromLocalInput(checkOut), shift_id: shiftId ? Number(shiftId) : null, note: note || null, reason }
      return rec ? send('PUT', `/api/v1/attendance/records/${rec.id}`, body) : send('POST', '/api/v1/attendance/records', { ...body, employee_id: employeeId, work_date: date })
    },
    onSuccess: () => done(t('common.saved')),
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/attendance/records/${rec?.id}?reason=${encodeURIComponent(reason)}`),
    onSuccess: () => done(t('attendance.record.deleted')),
    onError: (e) => setDeleteError(errorText(t, e)),
  })

  const fe = save.isError ? fieldErrors(t, save.error) : {}
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  const valid = !!checkIn && reason.trim().length >= 3

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={rec ? t('attendance.record.edit') : t('attendance.record.add')} subtitle={`${name} · ${date.split('-').reverse().join('.')}`} backTo={back} backLabel={t('attendance.daily.title')} />

      {rec && (
        <Card className="flex flex-wrap gap-2 p-4 text-sm">
          <Badge>{t('attendance.in')}: {fmtTime(rec.check_in_at)}</Badge>
          <Badge>{t('attendance.out')}: {fmtTime(rec.check_out_at)}</Badge>
          <Badge>{t('attendance.worked')}: {rec.check_out_at ? fmtMin(rec.worked_minutes) : '—'}</Badge>
          {rec.late_minutes > 0 && <Badge tone="warning">{t('attendance.my.late', { m: rec.late_minutes })}</Badge>}
          {rec.early_leave_minutes > 0 && <Badge tone="warning">{t('attendance.my.early', { m: rec.early_leave_minutes })}</Badge>}
          <Badge>{t(`attendance.method.${rec.in_method}`)}{rec.in_distance_m !== null ? ` · ${rec.in_distance_m} m` : ''}</Badge>
        </Card>
      )}

      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('attendance.record.sectionTimes')} description={t('attendance.record.timesHint')}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('attendance.in')} error={fe.check_in_at}>
              {(id) => <Input id={id} type="datetime-local" value={checkIn} onChange={(e) => setCheckIn(e.target.value)} required />}
            </Field>
            <Field label={t('attendance.out')} hint={t('attendance.record.outHint')}>
              {(id) => <Input id={id} type="datetime-local" value={checkOut} onChange={(e) => setCheckOut(e.target.value)} />}
            </Field>
          </div>
          <Field label={t('attendance.shift')} hint={t('attendance.record.shiftHint')}>
            {(id) => (
              <Select id={id} value={shiftId} onChange={(e) => setShiftId(e.target.value)}>
                <option value="">{t('attendance.record.noShift')}</option>
                {shifts.data
                  ?.filter((s) => s.is_active || String(s.id) === shiftId)
                  .map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} · {s.start_time}–{s.end_time}
                    </option>
                  ))}
              </Select>
            )}
          </Field>
          <Field label={t('employees.note')}>
            {(id) => <Input id={id} value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} />}
          </Field>
        </FormSection>

        <FormSection title={t('attendance.record.sectionReason')} description={t('attendance.record.reasonHint')}>
          <Field label={t('attendance.record.reason')} error={fe.reason}>
            {(id) => <Input id={id} value={reason} onChange={(e) => setReason(e.target.value)} required minLength={3} maxLength={500} placeholder={t('attendance.record.reasonPlaceholder')} />}
          </Field>
        </FormSection>

        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(back)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !valid}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>

      {rec && (
        <>
          <FormSection title={t('attendance.record.history')}>
            {rec.corrections.length === 0 && <p className="text-sm text-muted">{t('attendance.record.noHistory')}</p>}
            <ul className="flex flex-col gap-3">
              {rec.corrections.map((c) => (
                <li key={c.id} className="rounded-control border border-border p-3 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Badge tone={c.action === 'delete' ? 'danger' : 'neutral'}>{t(`attendance.record.actions.${c.action}`)}</Badge>
                    <span className="text-xs text-muted">{formatDateTime(c.created_at, i18n.language)}</span>
                  </div>
                  <p className="mt-2">{c.reason}</p>
                  {c.before && c.after && (
                    <p className="mt-1 text-xs text-muted">
                      {fmtTime(c.before.check_in_at as string)}–{fmtTime(c.before.check_out_at as string | null)} → {fmtTime(c.after.check_in_at as string)}–{fmtTime(c.after.check_out_at as string | null)}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </FormSection>

          <FormSection title={t('org.dangerZone')} description={t('attendance.record.deleteHint')} danger>
            <div className="flex flex-wrap items-center gap-3">
              <Button
                variant="outline"
                className="text-danger"
                disabled={remove.isPending || reason.trim().length < 3}
                onClick={async () => {
                  if (await confirm({ title: t('attendance.record.delete'), body: t('attendance.record.deleteConfirm', { name }), danger: true, confirmLabel: t('common.delete') })) {
                    setDeleteError(null)
                    remove.mutate()
                  }
                }}
              >
                <Trash2 className="size-4" />
                {t('attendance.record.delete')}
              </Button>
              {reason.trim().length < 3 && <span className="text-sm text-muted">{t('attendance.record.deleteNeedsReason')}</span>}
              {deleteError && (
                <span role="alert" className="text-sm text-danger">
                  {deleteError}
                </span>
              )}
            </div>
          </FormSection>
        </>
      )}
    </div>
  )
}
