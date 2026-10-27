import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { EmployeePicker, type Picked } from '../payroll/EmployeePicker'
import type { Permit } from './api'

const LIST = '/mobile/permits'

/** /mobile/permits/new va /mobile/permits/:eid/edit */
export function PermitFormPage() {
  const { eid } = useParams()
  const id = eid ? Number(eid) : null
  const q = useQuery({ queryKey: ['mobile', 'permit', id], queryFn: () => api<Permit>(`/api/v1/mobile/permits/${id}`), enabled: id !== null, retry: false })
  if (id === null) return <PermitForm p={null} />
  if (q.isLoading) return <Skeleton className="mx-auto h-72 max-w-3xl" />
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!q.data) return null
  return <PermitForm key={q.data.employee.id} p={q.data} />
}

function PermitForm({ p }: { p: Permit | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const [emp, setEmp] = useState<Picked | null>(p ? { id: p.employee.id, name: p.employee.name ?? '' } : null)
  const [enabled, setEnabled] = useState(p?.enabled ?? true)
  const [start, setStart] = useState(p?.window_start ?? '08:00')
  const [end, setEnd] = useState(p?.window_end ?? '20:00')
  const [interval, setIntervalS] = useState(String(p?.interval_s ?? 60))
  const [note, setNote] = useState(p?.note ?? '')
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const save = useMutation({
    mutationFn: () => send('PUT', `/api/v1/mobile/permits/${emp?.id}`, { enabled, interval_s: Number(interval) || 60, window_start: `${start}:00`, window_end: `${end}:00`, note: note || null }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['mobile'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(LIST, { replace: true })
    },
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/mobile/permits/${emp?.id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['mobile'] })
      toast.push({ title: t('mobile.permit.deleted'), tone: 'success' })
      navigate(LIST, { replace: true })
    },
    onError: (e) => setDeleteError(errorText(t, e)),
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={p?.exists ? t('mobile.permit.edit') : t('mobile.permit.add')} subtitle={p?.employee.name ?? undefined} backTo={LIST} backLabel={t('mobile.tabs.permits')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('payroll.line.employee')} description={t('mobile.permit.whoHint')}>
          <Field label={t('payroll.line.employee')}>{(id) => <EmployeePicker id={id} value={emp} onChange={setEmp} disabled={!!p} />}</Field>
        </FormSection>
        <FormSection title={t('mobile.permit.rules')} description={t('mobile.permit.rulesHint')}>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={t('mobile.permit.from')}>{(id) => <Input id={id} type="time" value={start} onChange={(e) => setStart(e.target.value)} required />}</Field>
            <Field label={t('mobile.permit.to')}>{(id) => <Input id={id} type="time" value={end} onChange={(e) => setEnd(e.target.value)} required />}</Field>
            <Field label={t('mobile.permit.interval')} hint={t('mobile.permit.intervalHint')}>{(id) => <Input id={id} type="number" min={15} max={600} value={interval} onChange={(e) => setIntervalS(e.target.value)} />}</Field>
          </div>
          <Field label={t('recruit.candidate.note')}>{(id) => <Input id={id} value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} />}</Field>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
            {t('mobile.permit.enabled')}
          </label>
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(LIST)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !emp || end <= start}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
      {p?.exists && (
        <FormSection title={t('org.dangerZone')} description={t('mobile.permit.deleteHint')} danger>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              className="text-danger"
              disabled={remove.isPending}
              onClick={async () => {
                if (await confirm({ title: t('mobile.permit.delete'), body: p.employee.name ?? '', danger: true, confirmLabel: t('common.delete') })) {
                  setDeleteError(null)
                  remove.mutate()
                }
              }}
            >
              <Trash2 className="size-4" />
              {t('mobile.permit.delete')}
            </Button>
            {deleteError && (
              <span role="alert" className="text-sm text-danger">
                {deleteError}
              </span>
            )}
          </div>
        </FormSection>
      )}
    </div>
  )
}
