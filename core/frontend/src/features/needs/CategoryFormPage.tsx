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
import { errorText, fieldErrors } from '../auth/errorText'
import { AssigneePicker } from './NeedPicker'
import type { Category, Person } from './api'

const LIST = '/needs/categories'

/** /needs/categories/new va /needs/categories/:id/edit */
export function CategoryFormPage() {
  const { id } = useParams()
  const catId = id ? Number(id) : null
  const q = useQuery({ queryKey: ['needs', 'category', catId], queryFn: () => api<Category>(`/api/v1/needs/categories/${catId}`), enabled: catId !== null, retry: false })
  if (catId === null) return <CategoryForm cat={null} />
  if (q.isLoading) return <Skeleton className="mx-auto h-72 max-w-3xl" />
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!q.data) return null
  return <CategoryForm key={q.data.id} cat={q.data} />
}

function CategoryForm({ cat }: { cat: Category | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const [name, setName] = useState(cat?.name ?? '')
  const [description, setDescription] = useState(cat?.description ?? '')
  const [assignee, setAssignee] = useState<Person | null>(cat?.default_assignee ?? null)
  const [sla, setSla] = useState(cat?.sla_days ? String(cat.sla_days) : '')
  const [order, setOrder] = useState(String(cat?.sort_order ?? 0))
  const [active, setActive] = useState(cat?.is_active ?? true)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const save = useMutation({
    mutationFn: () => {
      const body = { name, description: description || null, default_assignee_id: assignee?.id ?? null, sla_days: sla ? Number(sla) : null, sort_order: Number(order) || 0, is_active: active }
      return cat ? send('PUT', `/api/v1/needs/categories/${cat.id}`, body) : send('POST', '/api/v1/needs/categories', body)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['needs'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(LIST)
    },
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/needs/categories/${cat?.id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['needs'] })
      toast.push({ title: t('needs.categories.deleted'), tone: 'success' })
      navigate(LIST)
    },
    onError: (e) => setDeleteError(errorText(t, e)),
  })
  const fe = save.isError ? fieldErrors(t, save.error) : {}
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={cat ? t('needs.categories.edit') : t('needs.categories.add')} subtitle={cat?.name} backTo={LIST} backLabel={t('needs.categories.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('needs.form.main')}>
          <Field label={t('needs.categories.name')} error={fe.name}>{(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} autoFocus />}</Field>
          <Field label={t('needs.form.description')}>{(id) => <Input id={id} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={300} />}</Field>
          <Field label={t('needs.categories.defaultAssignee')} hint={t('needs.categories.defaultAssigneeHint')}>{(id) => <AssigneePicker id={id} value={assignee} onChange={setAssignee} />}</Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('needs.categories.sla')} hint={t('needs.categories.slaHint')}>{(id) => <Input id={id} type="number" min={1} max={365} value={sla} onChange={(e) => setSla(e.target.value)} />}</Field>
            <Field label={t('needs.categories.order')}>{(id) => <Input id={id} type="number" min={0} max={9999} value={order} onChange={(e) => setOrder(e.target.value)} />}</Field>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4" checked={active} onChange={(e) => setActive(e.target.checked)} />
            {t('schedule.activeLabel')}
          </label>
        </FormSection>
        <FormFooter error={save.isError && !Object.keys(fe).length ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(LIST)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !name.trim()}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
      {cat && (
        <FormSection title={t('org.dangerZone')} description={t('needs.categories.deleteHint')} danger>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              className="text-danger"
              disabled={remove.isPending}
              onClick={async () => {
                if (await confirm({ title: t('needs.categories.delete'), body: t('org.deleteConfirm', { name: cat.name }), danger: true, confirmLabel: t('common.delete') })) {
                  setDeleteError(null)
                  remove.mutate()
                }
              }}
            >
              <Trash2 className="size-4" />
              {t('needs.categories.delete')}
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
