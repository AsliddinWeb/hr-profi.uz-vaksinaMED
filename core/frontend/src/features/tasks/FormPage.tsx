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
import { fromLocalInput, toLocalInput } from '../attendance/api'
import { errorText, fieldErrors } from '../auth/errorText'
import { useCan, useMe } from '../auth/useAuth'
import { NotFound } from '../../pages/NotFound'
import { PersonPicker } from './PersonPicker'
import { PRIORITIES, type Person, type TaskDetail, type TaskItem, type TaskTemplate } from './api'

/** /tasks/new va /tasks/:id/edit */
export function FormPage() {
  const { id } = useParams()
  const taskId = id ? Number(id) : null
  const task = useQuery({ queryKey: ['tasks', 'one', taskId], queryFn: () => api<TaskDetail>(`/api/v1/tasks/${taskId}`), enabled: taskId !== null, retry: false })
  if (taskId === null) return <TaskForm task={null} />
  if (task.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (task.error instanceof ApiError && task.error.status === 404) return <NotFound />
  if (!task.data) return null
  return <TaskForm key={task.data.id} task={task.data} />
}

function TaskForm({ task }: { task: TaskDetail | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const can = useCan()
  const me = useMe().data
  const assignOthers = can('tasks.assign') || can('tasks.manage')
  const [title, setTitle] = useState(task?.title ?? '')
  const [description, setDescription] = useState(task?.description ?? '')
  const [priority, setPriority] = useState<string>(task?.priority ?? 'normal')
  const [due, setDue] = useState(toLocalInput(task?.due_at))
  const [assignee, setAssignee] = useState<Person[]>(task?.assignee ? [task.assignee] : me && !assignOthers ? [{ id: me.id, name: me.full_name }] : [])
  const [watchers, setWatchers] = useState<Person[]>(task?.watchers ?? [])
  const [labels, setLabels] = useState((task?.labels ?? []).join(', '))
  const [templateId, setTemplateId] = useState('')
  const templates = useQuery({ queryKey: ['tasks', 'templates'], queryFn: () => api<TaskTemplate[]>('/api/v1/tasks/templates'), enabled: !task })

  const applyTemplate = (idStr: string) => {
    setTemplateId(idStr)
    const tpl = templates.data?.find((x) => String(x.id) === idStr)
    if (!tpl) return
    setTitle(tpl.title)
    setDescription(tpl.description ?? '')
    setPriority(tpl.priority)
    setLabels(tpl.labels.join(', '))
    if (tpl.due_days !== null) setDue(toLocalInput(new Date(Date.now() + tpl.due_days * 86400000).toISOString()).slice(0, 10) + 'T18:00')
  }

  const save = useMutation({
    mutationFn: () => {
      const body = {
        title, description: description || null, priority, due_at: fromLocalInput(due), assignee_id: assignee[0]?.id ?? null,
        watchers: watchers.map((w) => w.id), labels: labels.split(',').map((s) => s.trim()).filter(Boolean), template_id: templateId ? Number(templateId) : null,
      } // fmt: skip
      return task ? send<TaskItem>('PUT', `/api/v1/tasks/${task.id}`, body) : send<TaskItem>('POST', '/api/v1/tasks', body)
    },
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['tasks'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(`/tasks/${r.id}`, { replace: true })
    },
  })
  const fe = save.isError ? fieldErrors(t, save.error) : {}
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={task ? t('tasks.edit') : t('tasks.new')} subtitle={task?.title} backTo={task ? `/tasks/${task.id}` : '/tasks/board'} backLabel={task ? task.title : t('tasks.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        {!task && templates.data && templates.data.length > 0 && (
          <FormSection title={t('tasks.form.fromTemplate')} description={t('tasks.form.fromTemplateHint')}>
            <Field label={t('tasks.form.template')}>
              {(id) => (
                <Select id={id} value={templateId} onChange={(e) => applyTemplate(e.target.value)}>
                  <option value="">{t('tasks.form.noTemplate')}</option>
                  {templates.data?.filter((x) => x.is_active).map((x) => (
                    <option key={x.id} value={x.id}>
                      {x.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </FormSection>
        )}
        <FormSection title={t('tasks.form.main')}>
          <Field label={t('tasks.form.title')} error={fe.title}>{(id) => <Input id={id} value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={200} autoFocus />}</Field>
          <Field label={t('tasks.form.description')}>
            {(id) => <textarea id={id} value={description} onChange={(e) => setDescription(e.target.value)} rows={6} maxLength={10000} className="w-full rounded-control border border-border bg-surface px-3 py-2 text-sm" />}
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
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
            <Field label={t('tasks.due')} hint={t('tasks.form.dueHint')}>{(id) => <Input id={id} type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} />}</Field>
          </div>
        </FormSection>
        <FormSection title={t('tasks.form.people')}>
          <Field label={t('tasks.assignee')} hint={assignOthers ? undefined : t('tasks.form.selfOnly')}>
            {(id) => (assignOthers ? <PersonPicker id={id} value={assignee} onChange={setAssignee} /> : <p className="text-sm">{assignee[0]?.name}</p>)}
          </Field>
          <Field label={t('tasks.watchers')} hint={t('tasks.form.watchersHint')}>{(id) => <PersonPicker id={id} value={watchers} onChange={setWatchers} multiple />}</Field>
          <Field label={t('tasks.form.labels')} hint={t('tasks.form.labelsHint')}>{(id) => <Input id={id} value={labels} onChange={(e) => setLabels(e.target.value)} placeholder="ombor, tezkor" />}</Field>
        </FormSection>
        <FormFooter error={save.isError && !Object.keys(fe).length ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(task ? `/tasks/${task.id}` : '/tasks/board')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !title.trim()}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
