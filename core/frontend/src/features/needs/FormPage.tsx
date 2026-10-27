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
import { fromLocalInput, toLocalInput } from '../attendance/api'
import { errorText, fieldErrors } from '../auth/errorText'
import { PRIORITIES, type Category, type Need, type NeedDetail } from './api'

/** /needs/new va /needs/:id/edit */
export function FormPage() {
  const { id } = useParams()
  const needId = id ? Number(id) : null
  const need = useQuery({ queryKey: ['needs', 'one', needId], queryFn: () => api<NeedDetail>(`/api/v1/needs/${needId}`), enabled: needId !== null, retry: false })
  if (needId === null) return <NeedForm need={null} />
  if (need.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (need.error instanceof ApiError && need.error.status === 404) return <NotFound />
  if (!need.data) return null
  return <NeedForm key={need.data.id} need={need.data} />
}

function NeedForm({ need }: { need: NeedDetail | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [title, setTitle] = useState(need?.title ?? '')
  const [description, setDescription] = useState(need?.description ?? '')
  const [categoryId, setCategoryId] = useState(String(need?.category?.id ?? ''))
  const [branchId, setBranchId] = useState(String(need?.branch?.id ?? ''))
  const [priority, setPriority] = useState<string>(need?.priority ?? 'normal')
  const [due, setDue] = useState(toLocalInput(need?.due_at))
  const cats = useQuery({ queryKey: ['needs', 'categories'], queryFn: () => api<Category[]>('/api/v1/needs/categories') })
  const branches = useQuery({ queryKey: ['needs', 'branches'], queryFn: () => api<{ id: number; name: string }[]>('/api/v1/needs/branches') })
  const cat = cats.data?.find((c) => String(c.id) === categoryId)

  const save = useMutation({
    mutationFn: () => {
      const body = { title, description: description || null, category_id: categoryId ? Number(categoryId) : null, branch_id: branchId ? Number(branchId) : null, priority, due_at: fromLocalInput(due) }
      return need ? send<Need>('PUT', `/api/v1/needs/${need.id}`, body) : send<Need>('POST', '/api/v1/needs', body)
    },
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['needs'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(`/needs/${r.id}`, { replace: true })
    },
  })
  const fe = save.isError ? fieldErrors(t, save.error) : {}
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={need ? t('needs.edit') : t('needs.new')} subtitle={need?.number} backTo={need ? `/needs/${need.id}` : '/needs'} backLabel={need ? need.number : t('needs.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('needs.form.main')}>
          <Field label={t('needs.form.title')} error={fe.title}>{(id) => <Input id={id} value={title} onChange={(e) => setTitle(e.target.value)} required minLength={3} maxLength={200} autoFocus />}</Field>
          <Field label={t('needs.form.description')}>
            {(id) => <textarea id={id} value={description} onChange={(e) => setDescription(e.target.value)} rows={6} maxLength={10000} className="w-full rounded-control border border-border bg-surface px-3 py-2 text-sm" />}
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('needs.category')} hint={cat ? [cat.default_assignee && t('needs.form.autoAssign', { name: cat.default_assignee.name }), cat.sla_days && t('needs.form.sla', { days: cat.sla_days })].filter(Boolean).join(' · ') : undefined}>
              {(id) => (
                <Select id={id} value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
                  <option value="">{t('needs.noCategory')}</option>
                  {cats.data?.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('needs.branch')}>
              {(id) => (
                <Select id={id} value={branchId} onChange={(e) => setBranchId(e.target.value)}>
                  <option value="">—</option>
                  {branches.data?.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('tasks.priorityLabel')}>
              {(id) => (
                <Select id={id} value={priority} onChange={(e) => setPriority(e.target.value)}>
                  {PRIORITIES.map((p) => (
                    <option key={p} value={p}>
                      {t(`tasks.priority.${p}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('needs.due')} hint={t('needs.form.dueHint')}>{(id) => <Input id={id} type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} />}</Field>
          </div>
        </FormSection>
        <FormFooter error={save.isError && !Object.keys(fe).length ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(need ? `/needs/${need.id}` : '/needs')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || title.trim().length < 3}>
            {need ? t('common.save') : t('needs.form.submit')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
