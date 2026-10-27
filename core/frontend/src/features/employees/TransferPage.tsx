import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { AssignmentFields } from './AssignmentFields'
import type { Assignment } from './assignment'
import { today, type Employee } from './api'

/** /employees/:id/transfer: bo'lim, lavozim yoki filialni o'zgartirish (tarixga yoziladi). */
export function TransferPage() {
  const { id } = useParams()
  const empId = Number(id)
  const emp = useQuery({ queryKey: ['employees', 'one', empId], queryFn: () => api<Employee>(`/api/v1/employees/${empId}`), retry: false })
  if (emp.isLoading) return <Skeleton className="mx-auto h-80 max-w-3xl" />
  if (emp.error instanceof ApiError && emp.error.status === 404) return <NotFound />
  return emp.data ? <TransferForm emp={emp.data} /> : null
}

function TransferForm({ emp }: { emp: Employee }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [value, setValue] = useState<Assignment>({
    departmentId: emp.department?.id.toString() ?? '',
    positionId: emp.position?.id.toString() ?? '',
    branchId: emp.branch?.id.toString() ?? '',
  })
  const [date, setDate] = useState(today())
  const [note, setNote] = useState('')
  const back = `/employees/${emp.id}`

  const save = useMutation({
    mutationFn: () =>
      send('POST', `/api/v1/employees/${emp.id}/transfer`, {
        department_id: value.departmentId ? Number(value.departmentId) : null,
        position_id: value.positionId ? Number(value.positionId) : null,
        branch_id: value.branchId ? Number(value.branchId) : null,
        effective_date: date,
        note: note || null,
      }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['employees'] })
      toast.push({ title: t('employees.transferred'), tone: 'success' })
      navigate(`${back}?tab=history`)
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={t('employees.transfer')} subtitle={emp.full_name} backTo={back} backLabel={t('employees.toCard')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('employees.currentAssignment')}>
          <p className="text-sm">
            {[emp.department?.name, emp.position?.name, emp.branch ? `${emp.branch.number ? `№${emp.branch.number} ` : ''}${emp.branch.name}` : null].filter(Boolean).join(' · ') || '—'}
          </p>
        </FormSection>
        <FormSection title={t('employees.newAssignment')} description={t('employees.transferHint')}>
          <AssignmentFields value={value} onChange={setValue} />
        </FormSection>
        <FormSection title={t('employees.sectionDetails')}>
          <Field label={t('employees.effectiveDate')}>{(id) => <Input id={id} type="date" value={date} onChange={(e) => setDate(e.target.value)} required className="max-w-52" />}</Field>
          <Field label={t('employees.note')}>
            {(id) => <textarea id={id} value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} rows={3} className="w-full rounded-control border border-border bg-surface px-3 py-2 text-sm" />}
          </Field>
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(back)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending}>
            {t('employees.transfer')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
