import { TaskStepper } from './TaskStepper'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlarmClock, Download, Paperclip, Pencil, Send, Trash2 } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { AiSummary } from '../ai/AiSummary'
import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Info } from '../../components/ui/Info'
import { Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send, upload } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { useMe } from '../auth/useAuth'
import { dueText, PRIORITY_TONE, sizeText, STATUSES, type BatchInfo, type Comment, type TaskDetail, type TaskFile, type TStatus } from './api'

type Tab = 'comments' | 'files' | 'history'

/** /tasks/:id: topshiriq tafsiloti, holat, izohlar (chat), fayllar va tarix. */
export function DetailPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const [tab, setTab] = useState<Tab>('comments')
  const q = useQuery({ queryKey: ['tasks', 'one', id], queryFn: () => api<TaskDetail>(`/api/v1/tasks/${id}`), retry: false, refetchInterval: 20_000 })
  const refresh = () => void qc.invalidateQueries({ queryKey: ['tasks'] })
  const move = useMutation({ mutationFn: (status: TStatus) => send('POST', `/api/v1/tasks/${id}/move`, { status }), onSuccess: refresh })
  const me = useMe().data
  const accept = useMutation({ mutationFn: () => send('POST', `/api/v1/tasks/${id}/accept`), onSuccess: refresh })
  const archive = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/tasks/${id}`),
    onSuccess: () => {
      refresh()
      toast.push({ title: t('tasks.archived'), tone: 'success' })
      navigate('/tasks/board')
    },
  })
  const batch = useQuery({ queryKey: ['tasks', 'batch', id], queryFn: () => api<BatchInfo>(`/api/v1/tasks/${id}/batch`), enabled: !!q.data?.batch_id, retry: false })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const task = q.data
  if (!task) return <Skeleton className="mx-auto h-96 max-w-4xl" />

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title={task.title}
        subtitle={`${t('tasks.creator')}: ${task.creator?.name ?? '—'} · ${formatDateTime(task.created_at, i18n.language)}`}
        backTo="/tasks/board"
        backLabel={t('tasks.title')}
        actions={
          <>
            <Link to={`/reminders/new?title=${encodeURIComponent(task.title)}&link=${encodeURIComponent(`/tasks/${id}`)}`}>
              <Button variant="outline">
                <AlarmClock className="size-4" />
                {t('reminders.remindMe')}
              </Button>
            </Link>
            {task.can_edit && (
            <>
              <Link to={`/tasks/${id}/edit`}>
                <Button variant="outline">
                  <Pencil className="size-4" />
                  {t('common.edit')}
                </Button>
              </Link>
              <Button
                variant="outline"
                className="text-danger"
                disabled={archive.isPending}
                onClick={async () => {
                  if (await confirm({ title: t('tasks.archive'), body: t('tasks.archiveConfirm'), danger: true, confirmLabel: t('tasks.archive') })) archive.mutate()
                }}
              >
                <Trash2 className="size-4" />
                {t('tasks.archive')}
              </Button>
            </>
            )}
          </>
        }
      />

      <AiSummary entity="task" id={id} />

      {batch.data && batch.data.total > 1 && (
        <Card className="flex flex-col gap-3 p-5">
          <h2 className="font-semibold">{t('tasks.chain.batchTitle', { n: batch.data.total })}</h2>
          <div className="flex flex-wrap gap-2 text-xs">
            {(['new', 'accepted', 'in_progress', 'review', 'done'] as const).map((s) => (
              <Badge key={s} tone={s === 'done' ? 'success' : 'neutral'}>
                {t(`tasks.chain.${s}`)}: {batch.data?.by_step[s] ?? 0}
              </Badge>
            ))}
          </div>
          <ul className="grid gap-1.5 text-sm sm:grid-cols-2">
            {batch.data.items.map((it) => (
              <li key={it.id}>
                <Link to={`/tasks/${it.id}`} className="flex items-center justify-between gap-2 rounded-control border border-border px-3 py-1.5 hover:bg-surface-2">
                  <span className="truncate">{it.assignee ?? '—'}</span>
                  <span className={it.overdue ? 'text-danger' : 'text-muted'}>{t(`tasks.chain.${it.step}`)}</span>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card className="flex flex-col gap-4 p-6">
        <TaskStepper step={task.step} overdue={task.overdue} />
        {task.step === 'new' && me?.id === task.assignee?.id && !task.archived && (
          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-primary/30 bg-primary/5 p-3">
            <span className="text-sm">{t('tasks.chain.acceptPrompt')}</span>
            <Button disabled={accept.isPending} onClick={() => accept.mutate()}>
              {t('tasks.chain.accept')}
            </Button>
          </div>
        )}
        {accept.isError && (
          <p role="alert" className="text-sm text-danger">
            {errorText(t, accept.error)}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded-md px-2 py-0.5 text-xs font-medium ${PRIORITY_TONE[task.priority]}`}>{t(`tasks.priority.${task.priority}`)}</span>
          {task.overdue && <Badge tone="danger">{t('tasks.overdue')}</Badge>}
          {task.labels.map((l) => (
            <Badge key={l}>{l}</Badge>
          ))}
        </div>
        <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-xs text-muted">{t('attendance.statusLabel')}</dt>
            <dd className="mt-1">
              <Select className="h-9 max-w-48" value={task.status} disabled={task.allowed_status.length === 0 || move.isPending} onChange={(e) => move.mutate(e.target.value as TStatus)} aria-label={t('attendance.statusLabel')}>
                {STATUSES.map((s) => (
                  <option key={s} value={s} disabled={s !== task.status && !task.allowed_status.includes(s)}>
                    {t(`tasks.status.${s}`)}
                  </option>
                ))}
              </Select>
            </dd>
          </div>
          <Info label={t('tasks.assignee')}>{task.assignee?.name ?? t('tasks.unassigned')}</Info>
          <Info label={t('tasks.due')} className={'tabular-nums ' + (task.overdue ? 'text-danger' : '')}>{task.due_at ? dueText(task.due_at) : null}</Info>
          {task.watchers.length > 0 && (
            <Info label={t('tasks.watchers')} className="sm:col-span-3">{task.watchers.map((w) => w.name).join(', ')}</Info>
          )}
        </dl>
        {move.isError && (
          <p role="alert" className="text-sm text-danger">
            {errorText(t, move.error)}
          </p>
        )}
        {task.status === 'review' && task.allowed_status.includes('done') && <p className="text-xs text-muted">{t('tasks.reviewHint')}</p>}
        {task.description && <p className="whitespace-pre-wrap border-t border-border pt-4 text-sm leading-relaxed">{task.description}</p>}
      </Card>

      <div className="flex gap-1 border-b border-border" role="tablist">
        {(['comments', 'files', 'history'] as const).map((k) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)} className={'-mb-px border-b-2 px-4 py-2 text-sm font-medium ' + (tab === k ? 'border-primary text-text' : 'border-transparent text-muted hover:text-text')}>
            {t(`tasks.tabs.${k}`)}
            {k === 'comments' && task.comments > 0 && <span className="ml-1.5 text-xs text-muted">{task.comments}</span>}
            {k === 'files' && task.files > 0 && <span className="ml-1.5 text-xs text-muted">{task.files}</span>}
          </button>
        ))}
      </div>

      {tab === 'comments' && <Chat taskId={id} canWrite={task.can_collaborate} />}
      {tab === 'files' && <Files taskId={id} canWrite={task.can_collaborate} canManage={task.can_edit} />}
      {tab === 'history' && (
        <Card className="p-6">
          <ol className="flex flex-col gap-4 border-l border-border pl-5">
            {task.events.map((e) => (
              <li key={e.id} className="relative text-sm">
                <span className="absolute -left-[26px] top-1.5 size-2.5 rounded-full bg-primary" aria-hidden />
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="font-medium">{eventText(t, e)}</span>
                  <span className="text-xs text-muted">{formatDateTime(e.created_at, i18n.language)}</span>
                </div>
                {e.actor && <div className="text-xs text-muted">{e.actor}</div>}
              </li>
            ))}
          </ol>
        </Card>
      )}
    </div>
  )
}

function eventText(t: (k: string, o?: Record<string, unknown>) => string, e: TaskDetail['events'][number]): string {
  const d = e.data ?? {}
  if (e.action === 'status') return t('tasks.event.status', { from: t(`tasks.status.${d.from}`), to: t(`tasks.status.${d.to}`) })
  if (e.action === 'updated') return t('tasks.event.updated', { fields: Object.keys(d).map((k) => t(`tasks.fields.${k}`, { defaultValue: k })).join(', ') })
  if (e.action === 'file_added' || e.action === 'file_removed') return t(`tasks.event.${e.action}`, { name: String(d.filename ?? '') })
  return t(`tasks.event.${e.action}`)
}

function Chat({ taskId, canWrite }: { taskId: number; canWrite: boolean }) {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const me = useMe().data?.id
  const [text, setText] = useState('')
  const end = useRef<HTMLDivElement>(null)
  const list = useQuery({ queryKey: ['tasks', 'comments', taskId], queryFn: () => api<Comment[]>(`/api/v1/tasks/${taskId}/comments`), refetchInterval: 8_000 })
  const send_ = useMutation({
    mutationFn: () => send<Comment>('POST', `/api/v1/tasks/${taskId}/comments`, { body: text }),
    onSuccess: () => {
      setText('')
      void qc.invalidateQueries({ queryKey: ['tasks'] })
    },
  })
  useEffect(() => {
    end.current?.scrollIntoView({ block: 'nearest' })
  }, [list.data?.length])
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (text.trim()) send_.mutate()
  }
  return (
    <Card className="flex flex-col gap-4 p-5">
      <ul className="flex max-h-[28rem] flex-col gap-3 overflow-y-auto" aria-live="polite">
        {list.data?.map((c) => {
          const mine = c.author.id === me
          return (
            <li key={c.id} className={'max-w-[85%] rounded-card px-4 py-2.5 text-sm ' + (mine ? 'self-end bg-primary text-primary-fg' : 'self-start bg-surface-2')}>
              <div className={'mb-0.5 text-xs ' + (mine ? 'text-primary-fg/80' : 'text-muted')}>
                {c.author.name} · {formatDateTime(c.created_at, i18n.language)}
              </div>
              <p className="whitespace-pre-wrap break-words">{c.body}</p>
            </li>
          )
        })}
        {list.data?.length === 0 && <li className="py-6 text-center text-sm text-muted">{t('tasks.noComments')}</li>}
        <div ref={end} />
      </ul>
      {canWrite && (
        <form onSubmit={submit} className="flex gap-2">
          <textarea value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && (e.metaKey || e.ctrlKey) && submit(e)} rows={2} maxLength={4000} placeholder={t('tasks.writeComment')} aria-label={t('tasks.writeComment')} className="min-h-11 flex-1 rounded-control border border-border bg-surface px-3 py-2 text-sm" />
          <Button type="submit" disabled={send_.isPending || !text.trim()} aria-label={t('tasks.send')}>
            <Send className="size-4" />
          </Button>
        </form>
      )}
      {send_.isError && (
        <p role="alert" className="text-sm text-danger">
          {errorText(t, send_.error)}
        </p>
      )}
    </Card>
  )
}

function Files({ taskId, canWrite, canManage }: { taskId: number; canWrite: boolean; canManage: boolean }) {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const confirm = useConfirm()
  const input = useRef<HTMLInputElement>(null)
  const me = useMe().data?.full_name
  const list = useQuery({ queryKey: ['tasks', 'files', taskId], queryFn: () => api<TaskFile[]>(`/api/v1/tasks/${taskId}/files`) })
  const refresh = () => void qc.invalidateQueries({ queryKey: ['tasks'] })
  const up = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return upload('POST', `/api/v1/tasks/${taskId}/files`, form)
    },
    onSuccess: refresh,
  })
  const del = useMutation({ mutationFn: (fid: number) => send('DELETE', `/api/v1/tasks/${taskId}/files/${fid}`), onSuccess: refresh })
  return (
    <Card className="flex flex-col gap-4 p-5">
      {canWrite && (
        <div>
          <input ref={input} type="file" className="sr-only" aria-label={t('tasks.attach')} onChange={(e) => (e.target.files?.[0] && up.mutate(e.target.files[0]), (e.target.value = ''))} />
          <Button variant="outline" disabled={up.isPending} onClick={() => input.current?.click()}>
            <Paperclip className="size-4" />
            {t('tasks.attach')}
          </Button>
          <span className="ml-3 text-xs text-muted">{t('tasks.attachHint')}</span>
        </div>
      )}
      {(up.isError || del.isError) && (
        <p role="alert" className="text-sm text-danger">
          {errorText(t, up.error ?? del.error)}
        </p>
      )}
      <ul className="divide-y divide-border text-sm">
        {list.data?.map((f) => (
          <li key={f.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
            <span className="min-w-0">
              <span className="block truncate font-medium">{f.filename}</span>
              <span className="text-xs text-muted">
                {sizeText(f.size)} · {f.uploaded_by} · {formatDateTime(f.created_at, i18n.language)}
              </span>
            </span>
            <span className="flex gap-1">
              <a href={`/api/v1/tasks/${taskId}/files/${f.id}`} download aria-label={t('tasks.download')}>
                <Button variant="ghost" className="h-8 px-2">
                  <Download className="size-4" />
                </Button>
              </a>
              {(canManage || f.uploaded_by === me) && (
                <Button
                  variant="ghost"
                  className="h-8 px-2 text-danger"
                  aria-label={t('common.delete')}
                  onClick={async () => {
                    if (await confirm({ title: t('tasks.deleteFile'), body: f.filename, danger: true, confirmLabel: t('common.delete') })) del.mutate(f.id)
                  }}
                >
                  <Trash2 className="size-4" />
                </Button>
              )}
            </span>
          </li>
        ))}
        {list.data?.length === 0 && <li className="py-6 text-center text-muted">{t('common.empty')}</li>}
      </ul>
    </Card>
  )
}
