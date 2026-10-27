import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { todayLocal } from '../attendance/api'
import { errorText } from '../auth/errorText'
import { AssignmentFields } from '../employees/AssignmentFields'
import type { Assignment } from '../employees/assignment'
import type { ApplicationDetail, CandidateDetail } from './api'

interface HireResult {
  employee_id: number
  employee_no: number
  vacancy_closed: boolean
}
interface Match {
  id: number
  full_name?: string
  name?: string
}

/** /recruit/applications/:id/hire: nomzodni xodimga aylantirish. */
export function HirePage() {
  const id = Number(useParams().id)
  const a = useQuery({ queryKey: ['recruit', 'application', id], queryFn: () => api<ApplicationDetail>(`/api/v1/recruit/applications/${id}`), retry: false })
  const c = useQuery({ queryKey: ['recruit', 'candidate', a.data?.candidate.id], queryFn: () => api<CandidateDetail>(`/api/v1/recruit/candidates/${a.data?.candidate.id}`), enabled: !!a.data })
  if (a.error instanceof ApiError && a.error.status === 404) return <NotFound />
  if (!a.data || !c.data) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  return <HireForm key={a.data.id} app={a.data} cand={c.data} />
}

function HireForm({ app, cand }: { app: ApplicationDetail; cand: CandidateDetail }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const parts = cand.full_name.split(/\s+/)
  const [last, setLast] = useState(parts[0] ?? '')
  const [first, setFirst] = useState(parts[1] ?? '')
  const [middle, setMiddle] = useState(parts.slice(2).join(' '))
  const [date, setDate] = useState(todayLocal())
  const [assign, setAssign] = useState<Assignment>({ departmentId: String(app.vacancy.department_id ?? ''), positionId: String(app.vacancy.position_id ?? ''), branchId: String(app.vacancy.branch_id ?? '') })
  const [confirmDup, setConfirmDup] = useState(false)
  const num = (s: string) => (s ? Number(s) : null)

  const hire = useMutation({
    mutationFn: () => send<HireResult>('POST', `/api/v1/recruit/applications/${app.id}/hire`, { last_name: last, first_name: first, middle_name: middle || null, hire_date: date, branch_id: num(assign.branchId), department_id: num(assign.departmentId), position_id: num(assign.positionId), confirm_duplicate: confirmDup }),
    onSuccess: (r) => {
      void qc.invalidateQueries()
      toast.push({ title: t('recruit.hire.done'), tone: 'success' })
      navigate(`/employees/${r.employee_id}`, { replace: true })
    },
  })
  const dup = hire.error instanceof ApiError && hire.error.code === 'possible_duplicate' ? ((hire.error.extra.matches as Match[]) ?? []) : null
  const submit = (e: FormEvent) => {
    e.preventDefault()
    hire.mutate()
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={t('recruit.application.hireBtn')} subtitle={cand.full_name} backTo={`/recruit/applications/${app.id}`} backLabel={cand.full_name} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('recruit.hire.person')} description={t('recruit.hire.personHint')}>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={t('recruit.hire.last')}>{(id) => <Input id={id} value={last} onChange={(e) => setLast(e.target.value)} required maxLength={80} />}</Field>
            <Field label={t('recruit.hire.first')}>{(id) => <Input id={id} value={first} onChange={(e) => setFirst(e.target.value)} required maxLength={80} />}</Field>
            <Field label={t('recruit.hire.middle')}>{(id) => <Input id={id} value={middle} onChange={(e) => setMiddle(e.target.value)} maxLength={80} />}</Field>
          </div>
          <Field label={t('recruit.hire.date')}>{(id) => <Input id={id} type="date" value={date} onChange={(e) => setDate(e.target.value)} required />}</Field>
        </FormSection>
        <FormSection title={t('recruit.hire.assignment')}>
          <AssignmentFields value={assign} onChange={setAssign} />
        </FormSection>
        {dup && (
          <Card tint="sand" className="flex flex-col gap-3 p-5 text-sm" role="alert">
            <p className="font-medium">{t('recruit.hire.duplicate')}</p>
            <ul className="list-disc pl-5">
              {dup.map((m) => (
                <li key={m.id}>
                  <Link to={`/employees/${m.id}`} className="hover:underline" target="_blank">
                    {m.full_name ?? m.name}
                  </Link>
                </li>
              ))}
            </ul>
            <label className="flex items-center gap-2">
              <input type="checkbox" className="size-4" checked={confirmDup} onChange={(e) => setConfirmDup(e.target.checked)} />
              {t('recruit.hire.confirmDuplicate')}
            </label>
          </Card>
        )}
        <FormFooter error={hire.isError && !dup ? errorText(t, hire.error) : null}>
          <Button variant="outline" onClick={() => navigate(`/recruit/applications/${app.id}`)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={hire.isPending || !last.trim() || !first.trim() || (!!dup && !confirmDup)}>
            {t('recruit.hire.submit')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
