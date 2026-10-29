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
  const [audDept, setAudDept] = useState('')
  const [audBranch, setAudBranch] = useState('')
  const [audGroup, setAudGroup] = useState('')
  const bulkMode = !task && assignOthers
  const departments = useQuery({ queryKey: ['org', 'departments-names'], queryFn: () => api<{ id: number; name: string }[]>('/api/v1/org/departments'), enabled: bulkMode && can('org.read'), retry: false })
  const branches = useQuery({ queryKey: ['branches', 'select'], queryFn: () => api<{ items: { id: number; name: string }[] }>('/api/v1/branches?size=200'), enabled: bulkMode && can('branches.read'), retry: false })
  const groups = useQuery({ queryKey: ['schedule', 'groups-names'], queryFn: () => api<{ id: number; name: string }[] | { items: { id: number; name: string }[] }>('/api/v1/schedule/groups'), enabled: bulkMode && can('schedule.read'), retry: false })
  const groupList = Array.isArray(groups.data) ? groups.data : (groups.data?.items ?? [])
  const audience = [audDept && `department_id=${audDept}`, audBranch && `branch_id=${audBranch}`, audGroup && `work_group_id=${audGroup}`].filter(Boolean).join('&')
  const preview = useQuery({ queryKey: ['tasks', 'audience', audience], queryFn: () => api<{ count: number; people: Person[] }>(`/api/v1/tasks/audience?${audience}`), enabled: bulkMode && !!audience, retry: false })
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

  type Bulk = { created: number; task_ids: number[] }
  const save = useMutation<TaskItem | Bulk>({
    mutationFn: () => {
      const body = {
        title, description: description || null, priority, due_at: fromLocalInput(due), assignee_id: assignee[0]?.id ?? null,
        watchers: watchers.map((w) => w.id), labels: labels.split(',').map((s) => s.trim()).filter(Boolean), template_id: templateId ? Number(templateId) : null,
      } // fmt: skip
      if (bulkMode && (assignee.length > 1 || audience)) {
        const { assignee_id: _unused, ...rest } = body
        void _unused
        return send<Bulk>('POST', '/api/v1/tasks/bulk', { ...rest, assignee_ids: assignee.map((a) => a.id), department_id: audDept ? Number(audDept) : null, branch_id: audBranch ? Number(audBranch) : null, work_group_id: audGroup ? Number(audGroup) : null })
      }
      return task ? send<TaskItem>('PUT', `/api/v1/tasks/${task.id}`, body) : send<TaskItem>('POST', '/api/v1/tasks', body)
    },
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['tasks'] })
      if ('task_ids' in r) {
        toast.push({ title: t('tasks.form.bulkCreated', { n: r.created }), tone: 'success' })
        navigate(r.task_ids.length === 1 ? `/tasks/${r.task_ids[0]}` : '/tasks', { replace: true })
        return
      }
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
        <FormSection title={t('tasks.form.people')} description={bulkMode ? t('tasks.form.bulkHint') : undefined}>
          <Field label={bulkMode ? t('tasks.form.assignees') : t('tasks.assignee')} hint={assignOthers ? undefined : t('tasks.form.selfOnly')}>
            {(id) => (assignOthers ? <PersonPicker id={id} value={assignee} onChange={setAssignee} multiple={bulkMode} max={bulkMode ? 50 : 1} /> : <p className="text-sm">{assignee[0]?.name}</p>)}
          </Field>
          {bulkMode && (can('org.read') || can('branches.read') || can('schedule.read')) && (
            <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface-2 p-4">
              <div className="text-sm font-medium">{t('tasks.form.audienceTitle')}</div>
              <div className="grid gap-3 sm:grid-cols-3">
                {can('org.read') && (
                  <Select value={audDept} onChange={(e) => setAudDept(e.target.value)} aria-label={t('tasks.form.department')}>
                    <option value="">{t('tasks.form.department')}</option>
                    {departments.data?.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name}
                      </option>
                    ))}
                  </Select>
                )}
                {can('branches.read') && (
                  <Select value={audBranch} onChange={(e) => setAudBranch(e.target.value)} aria-label={t('tasks.form.branch')}>
                    <option value="">{t('tasks.form.branch')}</option>
                    {branches.data?.items.map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.name}
                      </option>
                    ))}
                  </Select>
                )}
                {can('schedule.read') && (
                  <Select value={audGroup} onChange={(e) => setAudGroup(e.target.value)} aria-label={t('tasks.form.group')}>
                    <option value="">{t('tasks.form.group')}</option>
                    {groupList.map((g) => (
                      <option key={g.id} value={g.id}>
                        {g.name}
                      </option>
                    ))}
                  </Select>
                )}
              </div>
              {preview.data && (
                <p className="text-sm text-muted">
                  {t('tasks.form.audienceCount', { n: preview.data.count })}
                  {preview.data.people.length > 0 && `: ${preview.data.people.map((p) => p.name).join(', ')}${preview.data.count > preview.data.people.length ? '…' : ''}`}
                </p>
              )}
              <p className="text-xs text-muted">{t('tasks.form.separateHint')}</p>
            </div>
          )}
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
