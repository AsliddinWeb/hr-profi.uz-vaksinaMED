import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { DISMISS_REASONS, today, type Employee } from './api'

function useEmployee() {
  const empId = Number(useParams().id)
  const q = useQuery({ queryKey: ['employees', 'one', empId], queryFn: () => api<Employee>(`/api/v1/employees/${empId}`), retry: false })
  return { empId, ...q }
}

const textarea = 'w-full rounded-control border border-border bg-surface px-3 py-2 text-sm'

/** /employees/:id/dismiss */
export function DismissPage() {
  const { empId, data, isLoading, error } = useEmployee()
  if (isLoading) return <Skeleton className="mx-auto h-80 max-w-3xl" />
  if (error instanceof ApiError && error.status === 404) return <NotFound />
  return data ? <DismissForm key={empId} emp={data} /> : null
}

function DismissForm({ emp }: { emp: Employee }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [date, setDate] = useState(today())
  const [reason, setReason] = useState<string>('own_will')
  const [note, setNote] = useState('')
  const [block, setBlock] = useState(true)
  const back = `/employees/${emp.id}`

  const save = useMutation({
    mutationFn: () => send('POST', `/api/v1/employees/${emp.id}/dismiss`, { date, reason, note: note || null, block_account: block }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['employees'] })
      toast.push({ title: t('employees.dismissed'), tone: 'success' })
      navigate(back)
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={t('employees.dismiss')} subtitle={emp.full_name} backTo={back} backLabel={t('employees.toCard')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('employees.sectionDetails')} description={t('employees.dismissHint')}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('employees.dismissalDate')}>
              {(id) => <Input id={id} type="date" value={date} max={today()} min={emp.hire_date ?? undefined} onChange={(e) => setDate(e.target.value)} required />}
            </Field>
            <Field label={t('employees.dismissalReason')}>
              {(id) => (
                <Select id={id} value={reason} onChange={(e) => setReason(e.target.value)}>
                  {DISMISS_REASONS.map((r) => (
                    <option key={r} value={r}>
                      {t(`employees.reasons.${r}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
          <Field label={t('employees.note')} hint={reason === 'other' ? t('employees.noteRequired') : undefined}>
            {(id) => <textarea id={id} value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} rows={3} className={textarea} required={reason === 'other'} />}
          </Field>
        </FormSection>
        {emp.user && (
          <FormSection title={t('employees.sectionAccount')}>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="size-4" checked={block} onChange={(e) => setBlock(e.target.checked)} />
              {t('employees.blockAccount', { login: emp.user.login })}
            </label>
          </FormSection>
        )}
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(back)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || (reason === 'other' && !note.trim())} className="bg-danger text-white hover:opacity-90">
            {t('employees.dismiss')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}

/** /employees/:id/reinstate */
export function ReinstatePage() {
  const { empId, data, isLoading, error } = useEmployee()
  if (isLoading) return <Skeleton className="mx-auto h-80 max-w-3xl" />
  if (error instanceof ApiError && error.status === 404) return <NotFound />
  return data ? <ReinstateForm key={empId} emp={data} /> : null
}

function ReinstateForm({ emp }: { emp: Employee }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [date, setDate] = useState(today())
  const [note, setNote] = useState('')
  const [reactivate, setReactivate] = useState(true)
  const back = `/employees/${emp.id}`

  const save = useMutation({
    mutationFn: () => send('POST', `/api/v1/employees/${emp.id}/reinstate`, { date, note: note || null, reactivate_account: reactivate }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['employees'] })
      toast.push({ title: t('employees.reinstated'), tone: 'success' })
      navigate(back)
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={t('employees.reinstate')} subtitle={emp.full_name} backTo={back} backLabel={t('employees.toCard')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('employees.sectionDetails')} description={t('employees.reinstateHint')}>
          <Field label={t('employees.effectiveDate')}>
            {(id) => <Input id={id} type="date" value={date} min={emp.dismissal_date ?? undefined} onChange={(e) => setDate(e.target.value)} required className="max-w-52" />}
          </Field>
          <Field label={t('employees.note')}>
            {(id) => <textarea id={id} value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} rows={3} className={textarea} />}
          </Field>
          {emp.user && !emp.user.is_active && (
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="size-4" checked={reactivate} onChange={(e) => setReactivate(e.target.checked)} />
              {t('employees.reactivateAccount', { login: emp.user.login })}
            </label>
          )}
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(back)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending}>
            {t('employees.reinstate')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
