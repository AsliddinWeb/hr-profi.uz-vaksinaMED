import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText, fieldErrors } from '../auth/errorText'
import { AssignmentFields } from '../employees/AssignmentFields'
import type { Assignment } from '../employees/assignment'
import type { Vacancy } from './api'

const area = 'w-full rounded-control border border-border bg-surface px-3 py-2 text-sm'

/** /recruit/vacancies/new va /recruit/vacancies/:id/edit */
export function VacancyFormPage() {
  const { id } = useParams()
  const vid = id ? Number(id) : null
  const q = useQuery({ queryKey: ['recruit', 'vacancy', vid], queryFn: () => api<Vacancy>(`/api/v1/recruit/vacancies/${vid}`), enabled: vid !== null, retry: false })
  if (vid === null) return <VacancyForm v={null} />
  if (q.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!q.data) return null
  return <VacancyForm key={q.data.id} v={q.data} />
}

function VacancyForm({ v }: { v: Vacancy | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const back = v ? `/recruit/vacancies/${v.id}` : '/recruit/vacancies'
  const [title, setTitle] = useState(v?.title ?? '')
  const [assign, setAssign] = useState<Assignment>({ departmentId: String(v?.department?.id ?? ''), positionId: String(v?.position?.id ?? ''), branchId: String(v?.branch?.id ?? '') })
  const [description, setDescription] = useState(v?.description ?? '')
  const [requirements, setRequirements] = useState(v?.requirements ?? '')
  const [from, setFrom] = useState(v?.salary_from?.toString() ?? '')
  const [to, setTo] = useState(v?.salary_to?.toString() ?? '')
  const [openings, setOpenings] = useState(String(v?.openings ?? 1))
  const [recruiter, setRecruiter] = useState(String(v?.recruiter?.id ?? ''))
  const [deadline, setDeadline] = useState(v?.deadline ?? '')
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const recruiters = useQuery({ queryKey: ['recruit', 'recruiters'], queryFn: () => api<{ id: number; name: string }[]>('/api/v1/recruit/recruiters') })
  const num = (s: string) => (s.trim() === '' ? null : Number(s))

  const save = useMutation({
    mutationFn: () => {
      const body = {
        title, description: description || null, requirements: requirements || null, salary_from: num(from), salary_to: num(to), openings: Number(openings) || 1,
        branch_id: num(assign.branchId), department_id: num(assign.departmentId), position_id: num(assign.positionId), recruiter_id: num(recruiter), deadline: deadline || null,
      } // fmt: skip
      return v ? send<Vacancy>('PUT', `/api/v1/recruit/vacancies/${v.id}`, body) : send<Vacancy>('POST', '/api/v1/recruit/vacancies', body)
    },
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['recruit'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(`/recruit/vacancies/${r.id}`, { replace: true })
    },
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/recruit/vacancies/${v?.id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['recruit'] })
      toast.push({ title: t('recruit.vacancy.deleted'), tone: 'success' })
      navigate('/recruit/vacancies', { replace: true })
    },
    onError: (e) => setDeleteError(errorText(t, e)),
  })
  const fe = save.isError ? fieldErrors(t, save.error) : {}
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={v ? t('recruit.vacancy.edit') : t('recruit.vacancy.add')} subtitle={v?.title} backTo={back} backLabel={v ? v.title : t('recruit.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('needs.form.main')}>
          <Field label={t('recruit.vacancy.titleLabel')} error={fe.title}>{(id) => <Input id={id} value={title} onChange={(e) => setTitle(e.target.value)} required minLength={2} maxLength={200} autoFocus />}</Field>
          <AssignmentFields value={assign} onChange={setAssign} />
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={t('recruit.vacancy.openings')}>{(id) => <Input id={id} type="number" min={1} max={500} value={openings} onChange={(e) => setOpenings(e.target.value)} />}</Field>
            <Field label={t('recruit.vacancy.salaryFrom')}>{(id) => <Input id={id} type="number" min={0} value={from} onChange={(e) => setFrom(e.target.value)} />}</Field>
            <Field label={t('recruit.vacancy.salaryTo')} error={fe.salary_to}>{(id) => <Input id={id} type="number" min={0} value={to} onChange={(e) => setTo(e.target.value)} />}</Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('recruit.vacancy.recruiter')}>
              {(id) => (
                <Select id={id} value={recruiter} onChange={(e) => setRecruiter(e.target.value)}>
                  <option value="">—</option>
                  {recruiters.data?.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('recruit.vacancy.deadline')}>{(id) => <Input id={id} type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} />}</Field>
          </div>
        </FormSection>
        <FormSection title={t('recruit.vacancy.details')}>
          <Field label={t('needs.form.description')}>{(id) => <textarea id={id} value={description} onChange={(e) => setDescription(e.target.value)} rows={5} maxLength={10000} className={area} />}</Field>
          <Field label={t('recruit.vacancy.requirements')}>{(id) => <textarea id={id} value={requirements} onChange={(e) => setRequirements(e.target.value)} rows={5} maxLength={10000} className={area} />}</Field>
        </FormSection>
        <FormFooter error={save.isError && !Object.keys(fe).length ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(back)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || title.trim().length < 2}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
      {v && (
        <FormSection title={t('org.dangerZone')} description={t('recruit.vacancy.deleteHint')} danger>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              className="text-danger"
              disabled={remove.isPending}
              onClick={async () => {
                if (await confirm({ title: t('recruit.vacancy.delete'), body: t('org.deleteConfirm', { name: v.title }), danger: true, confirmLabel: t('common.delete') })) {
                  setDeleteError(null)
                  remove.mutate()
                }
              }}
            >
              <Trash2 className="size-4" />
              {t('recruit.vacancy.delete')}
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
