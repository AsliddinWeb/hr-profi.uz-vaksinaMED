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
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { PRIORITIES, PRIORITY_TONE, type TaskTemplate } from './api'

/** /tasks/templates: topshiriq shablonlari. */
export function TemplatesPage() {
  const { t } = useTranslation()
  const list = useQuery({ queryKey: ['tasks', 'templates'], queryFn: () => api<TaskTemplate[]>('/api/v1/tasks/templates') })
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title={t('tasks.templates.title')}
        subtitle={t('tasks.templates.subtitle')}
        actions={
          <Link to="/tasks/templates/new">
            <Button>
              <Plus className="size-4" />
              {t('tasks.templates.add')}
            </Button>
          </Link>
        }
      />
      {list.isLoading && <Skeleton className="h-32" />}
      <div className="grid gap-4 md:grid-cols-2">
        {list.data?.map((x) => (
          <Link key={x.id} to={`/tasks/templates/${x.id}/edit`}>
            <Card className={`h-full p-5 transition-shadow hover:shadow-lg ${x.is_active ? '' : 'opacity-60'}`}>
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <h3 className="truncate font-semibold">{x.name}</h3>
                  <p className="truncate text-xs text-muted">{x.title}</p>
                </div>
                <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${PRIORITY_TONE[x.priority]}`}>{t(`tasks.priority.${x.priority}`)}</span>
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {x.due_days !== null && <Badge>{t('tasks.templates.dueDays', { count: x.due_days })}</Badge>}
                {x.labels.map((l) => (
                  <Badge key={l}>{l}</Badge>
                ))}
                {!x.is_active && <Badge>{t('schedule.inactive')}</Badge>}
              </div>
            </Card>
          </Link>
        ))}
      </div>
      {list.data?.length === 0 && <p className="py-10 text-center text-muted">{t('common.empty')}</p>}
    </div>
  )
}

/** /tasks/templates/new va /tasks/templates/:id/edit */
export function TemplateFormPage() {
  const { id } = useParams()
  const tid = id ? Number(id) : null
  const tpl = useQuery({ queryKey: ['tasks', 'templates', tid], queryFn: () => api<TaskTemplate>(`/api/v1/tasks/templates/${tid}`), enabled: tid !== null, retry: false })
  if (tid === null) return <TemplateForm tpl={null} />
  if (tpl.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (tpl.error instanceof ApiError && tpl.error.status === 404) return <NotFound />
  if (!tpl.data) return null
  return <TemplateForm key={tpl.data.id} tpl={tpl.data} />
}

function TemplateForm({ tpl }: { tpl: TaskTemplate | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const LIST = '/tasks/templates'
  const [name, setName] = useState(tpl?.name ?? '')
  const [title, setTitle] = useState(tpl?.title ?? '')
  const [description, setDescription] = useState(tpl?.description ?? '')
  const [priority, setPriority] = useState<string>(tpl?.priority ?? 'normal')
  const [dueDays, setDueDays] = useState(tpl?.due_days?.toString() ?? '')
  const [labels, setLabels] = useState((tpl?.labels ?? []).join(', '))
  const [active, setActive] = useState(tpl?.is_active ?? true)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const save = useMutation({
    mutationFn: () => {
      const body = { name, title, description: description || null, priority, due_days: dueDays !== '' ? Number(dueDays) : null, labels: labels.split(',').map((s) => s.trim()).filter(Boolean), is_active: active }
      return tpl ? send('PUT', `/api/v1/tasks/templates/${tpl.id}`, body) : send('POST', '/api/v1/tasks/templates', body)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['tasks'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(LIST)
    },
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/tasks/templates/${tpl?.id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['tasks'] })
      toast.push({ title: t('tasks.templates.deleted'), tone: 'success' })
      navigate(LIST)
    },
    onError: (e) => setDeleteError(errorText(t, e)),
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={tpl ? t('tasks.templates.edit') : t('tasks.templates.add')} subtitle={tpl?.name} backTo={LIST} backLabel={t('tasks.templates.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('tasks.form.main')}>
          <Field label={t('tasks.templates.name')}>{(fid) => <Input id={fid} value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} autoFocus />}</Field>
          <Field label={t('tasks.form.title')}>{(fid) => <Input id={fid} value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={200} />}</Field>
          <Field label={t('tasks.form.description')}>{(fid) => <textarea id={fid} value={description} onChange={(e) => setDescription(e.target.value)} rows={5} maxLength={10000} className="w-full rounded-control border border-border bg-surface px-3 py-2 text-sm" />}</Field>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={t('tasks.priorityLabel')}>
              {(fid) => (
                <Select id={fid} value={priority} onChange={(e) => setPriority(e.target.value)}>
                  {PRIORITIES.map((p) => (
                    <option key={p} value={p}>
                      {t(`tasks.priority.${p}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('tasks.templates.dueDaysLabel')} hint={t('tasks.templates.dueDaysHint')}>{(fid) => <Input id={fid} type="number" min={0} max={365} value={dueDays} onChange={(e) => setDueDays(e.target.value)} />}</Field>
            <Field label={t('tasks.form.labels')}>{(fid) => <Input id={fid} value={labels} onChange={(e) => setLabels(e.target.value)} />}</Field>
          </div>
          {tpl && (
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="size-4" checked={active} onChange={(e) => setActive(e.target.checked)} />
              {t('schedule.activeLabel')}
            </label>
          )}
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(LIST)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !name.trim() || !title.trim()}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
      {tpl && (
        <FormSection title={t('org.dangerZone')} description={t('tasks.templates.deleteHint')} danger>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              className="text-danger"
              disabled={remove.isPending}
              onClick={async () => {
                if (await confirm({ title: t('tasks.templates.delete'), body: t('org.deleteConfirm', { name: tpl.name }), danger: true, confirmLabel: t('common.delete') })) {
                  setDeleteError(null)
                  remove.mutate()
                }
              }}
            >
              <Trash2 className="size-4" />
              {t('tasks.templates.delete')}
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
