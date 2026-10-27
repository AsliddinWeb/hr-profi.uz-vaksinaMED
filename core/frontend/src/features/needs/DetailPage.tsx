import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlarmClock, Check, Download, Paperclip, Pencil, Send, Star, Trash2 } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { AiSummary } from '../ai/AiSummary'
import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Info } from '../../components/ui/Info'
import { Stepper as UiStepper } from '../../components/ui/Stepper'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { api, ApiError, send, upload } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { useMe } from '../auth/useAuth'
import { dueText } from '../tasks/api'
import { AssigneePicker } from './NeedPicker'
import { PRIORITY_TONE, sizeText, STAGES, STATUS_TONE, type NeedComment, type NeedDetail, type NeedFile, type Person } from './api'

type Tab = 'comments' | 'files' | 'history'
const area = 'w-full rounded-control border border-border bg-surface px-3 py-2 text-sm'

/** /needs/:id: 4 bosqichli oqim, bosqich amallari (sahifa ichida), izoh, fayl va tarix. */
export function DetailPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const [tab, setTab] = useState<Tab>('comments')
  const q = useQuery({ queryKey: ['needs', 'one', id], queryFn: () => api<NeedDetail>(`/api/v1/needs/${id}`), retry: false, refetchInterval: 20_000 })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const n = q.data
  if (!n) return <Skeleton className="mx-auto h-96 max-w-4xl" />
  const showActions = n.can.assign || n.can.complete || n.can.confirm || n.can.cancel

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title={n.title}
        subtitle={`${n.number} · ${n.requester?.name ?? '—'} · ${formatDateTime(n.requested_at, i18n.language)}`}
        backTo="/needs"
        backLabel={t('needs.title')}
        actions={
          <>
            <Link to={`/reminders/new?title=${encodeURIComponent(n.title)}&link=${encodeURIComponent(`/needs/${id}`)}`}>
              <Button variant="outline">
                <AlarmClock className="size-4" />
                {t('reminders.remindMe')}
              </Button>
            </Link>
            {n.can.edit && (
              <Link to={`/needs/${id}/edit`}>
                <Button variant="outline">
                  <Pencil className="size-4" />
                  {t('common.edit')}
                </Button>
              </Link>
            )}
          </>
        }
      />

      <Stepper n={n} />

      <Card className="flex flex-col gap-4 p-6">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={STATUS_TONE[n.status]}>{t(`needs.status.${n.status}`)}</Badge>
          <span className={`rounded-md px-2 py-0.5 text-xs font-medium ${PRIORITY_TONE[n.priority]}`}>{t(`tasks.priority.${n.priority}`)}</span>
          {n.overdue && <Badge tone="danger">{t('needs.overdue')}</Badge>}
          {n.return_count > 0 && <Badge tone="warning">{t('needs.returnedTimes', { count: n.return_count })}</Badge>}
        </div>
        <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
          <Info label={t('needs.category')}>{n.category?.name ?? '—'}</Info>
          <Info label={t('needs.branch')}>{n.branch?.name ?? '—'}</Info>
          <Info label={t('needs.assignee')}>{n.assignee?.name ?? t('needs.unassigned')}</Info>
          <Info label={t('needs.due')}>
            <span className={'tabular-nums ' + (n.overdue ? 'font-semibold text-danger' : '')}>{n.due_at ? dueText(n.due_at) : '—'}</span>
          </Info>
          {n.rating !== null && (
            <Info label={t('needs.rating')}>
              <Stars value={n.rating} />
            </Info>
          )}
        </dl>
        {n.description && <p className="whitespace-pre-wrap border-t border-border pt-4 text-sm leading-relaxed">{n.description}</p>}
        {n.report && (
          <div className="rounded-control bg-surface-2 p-4 text-sm">
            <div className="mb-1 text-xs font-medium text-muted">{t('needs.report')}</div>
            <p className="whitespace-pre-wrap">{n.report}</p>
          </div>
        )}
        {n.confirm_note && (
          <div className="rounded-control bg-surface-2 p-4 text-sm">
            <div className="mb-1 text-xs font-medium text-muted">{t('needs.confirmNote')}</div>
            <p className="whitespace-pre-wrap">{n.confirm_note}</p>
          </div>
        )}
      </Card>

      <AiSummary entity="need" id={id} />
      {showActions && <Actions n={n} />}

      <div className="flex gap-1 border-b border-border" role="tablist">
        {(['comments', 'files', 'history'] as const).map((k) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)} className={'-mb-px border-b-2 px-4 py-2 text-sm font-medium ' + (tab === k ? 'border-primary text-text' : 'border-transparent text-muted hover:text-text')}>
            {t(`tasks.tabs.${k}`)}
            {k === 'comments' && n.comments > 0 && <span className="ml-1.5 text-xs text-muted">{n.comments}</span>}
            {k === 'files' && n.files > 0 && <span className="ml-1.5 text-xs text-muted">{n.files}</span>}
          </button>
        ))}
      </div>

      {tab === 'comments' && <Chat needId={id} canWrite={n.can.collaborate} />}
      {tab === 'files' && <Files needId={id} canWrite={n.can.collaborate} />}
      {tab === 'history' && (
        <Card className="p-6">
          <ol className="flex flex-col gap-4 border-l border-border pl-5">
            {n.events.map((e) => (
              <li key={e.id} className="relative text-sm">
                <span className="absolute -left-[26px] top-1.5 size-2.5 rounded-full bg-primary" aria-hidden />
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="font-medium">{eventText(t, e)}</span>
                  <span className="text-xs text-muted">{formatDateTime(e.created_at, i18n.language)}</span>
                </div>
                {e.actor && <div className="text-xs text-muted">{e.actor}</div>}
                {e.note && <p className="mt-1 whitespace-pre-wrap text-muted">{e.note}</p>}
              </li>
            ))}
          </ol>
        </Card>
      )}
    </div>
  )
}

function Stars({ value }: { value: number }) {
  return (
    <span className="inline-flex" aria-label={`${value}/5`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <Star key={i} className={'size-4 ' + (i <= value ? 'fill-warning text-warning' : 'text-border')} />
      ))}
    </span>
  )
}

function eventText(t: (k: string, o?: Record<string, unknown>) => string, e: NeedDetail['events'][number]): string {
  const d = e.data ?? {}
  if (e.action === 'assigned' && d.auto) return t('needs.event.autoAssigned')
  if (e.action === 'file_added' || e.action === 'file_removed') return t(`needs.event.${e.action}`, { name: String(d.filename ?? '') })
  return t(`needs.event.${e.action}`)
}

/** 4 bosqich: so'rash → ijrochi → bajarish → tasdiq. */
function Stepper({ n }: { n: NeedDetail }) {
  const { t, i18n } = useTranslation()
  const at: Record<string, string | null> = { requested: n.requested_at, assigned: n.assigned_at, completed: n.completed_at, confirmed: n.confirmed_at }
  const cur = n.status === 'cancelled' ? -1 : STAGES.indexOf(n.status)
  return (
    <Card className="p-6">
      <UiStepper
        label={t('needs.stages')}
        current={cur}
        cancelled={n.status === 'cancelled'}
        steps={STAGES.map((s) => ({ key: s, label: t(`needs.stage.${s}`), at: at[s] ? formatDateTime(at[s], i18n.language) : null }))}
      />
      {n.status === 'cancelled' && <p className="mt-4 text-center text-sm text-danger">{t('needs.cancelledHint')}</p>}
    </Card>
  )
}

/** Bosqich amallari: ijrochi tayinlash, bajarish, tasdiqlash/qaytarish, bekor qilish. */
function Actions({ n }: { n: NeedDetail }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const confirm = useConfirm()
  const [assignee, setAssignee] = useState<Person | null>(null)
  const [note, setNote] = useState('')
  const [report, setReport] = useState('')
  const [rating, setRating] = useState(0)
  const [reason, setReason] = useState('')
  const done = () => {
    setNote('')
    setReport('')
    setReason('')
    setRating(0)
    setAssignee(null)
    void qc.invalidateQueries({ queryKey: ['needs'] })
  }
  const act = useMutation({ mutationFn: ({ path, body }: { path: string; body: unknown }) => send('POST', `/api/v1/needs/${n.id}/${path}`, body), onSuccess: done })

  return (
    <Card className="flex flex-col gap-6 p-6">
      {n.can.assign && (
        <section className="flex flex-col gap-3" aria-labelledby="need-assign">
          <h2 id="need-assign" className="text-[15px] font-medium">{n.assignee ? t('needs.actions.reassign') : t('needs.actions.assign')}</h2>
          <AssigneePicker value={assignee} onChange={setAssignee} />
          <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={1000} placeholder={t('needs.actions.assignNote')} aria-label={t('needs.actions.assignNote')} className={area} />
          <div>
            <Button disabled={!assignee || act.isPending} onClick={() => assignee && act.mutate({ path: 'assign', body: { assignee_id: assignee.id, note: note || null } })}>
              {t('needs.actions.assignBtn')}
            </Button>
          </div>
        </section>
      )}
      {n.can.complete && (
        <section className="flex flex-col gap-3" aria-labelledby="need-complete">
          <h2 id="need-complete" className="text-[15px] font-medium">{t('needs.actions.complete')}</h2>
          <textarea value={report} onChange={(e) => setReport(e.target.value)} rows={4} maxLength={10000} placeholder={t('needs.actions.reportHint')} aria-label={t('needs.report')} className={area} />
          <p className="text-xs text-muted">{t('needs.actions.reportFiles')}</p>
          <div>
            <Button disabled={report.trim().length < 3 || act.isPending} onClick={() => act.mutate({ path: 'complete', body: { report } })}>
              <Check className="size-4" />
              {t('needs.actions.completeBtn')}
            </Button>
          </div>
        </section>
      )}
      {n.can.confirm && (
        <section className="flex flex-col gap-3" aria-labelledby="need-confirm">
          <h2 id="need-confirm" className="text-[15px] font-medium">{t('needs.actions.confirm')}</h2>
          <div className="flex items-center gap-1" role="radiogroup" aria-label={t('needs.rating')}>
            {[1, 2, 3, 4, 5].map((i) => (
              <button key={i} type="button" role="radio" aria-checked={rating === i} aria-label={`${i}`} onClick={() => setRating(rating === i ? 0 : i)}>
                <Star className={'size-6 ' + (i <= rating ? 'fill-warning text-warning' : 'text-border')} />
              </button>
            ))}
          </div>
          <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={1000} placeholder={t('needs.actions.confirmNote')} aria-label={t('needs.confirmNote')} className={area} />
          <div className="flex flex-wrap gap-2">
            <Button disabled={act.isPending} onClick={() => act.mutate({ path: 'confirm', body: { rating: rating || null, note: note || null } })}>
              <Check className="size-4" />
              {t('needs.actions.confirmBtn')}
            </Button>
          </div>
          <div className="flex flex-col gap-2 border-t border-border pt-4">
            <h3 className="text-sm font-medium">{t('needs.actions.return')}</h3>
            <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} maxLength={1000} placeholder={t('needs.actions.returnHint')} aria-label={t('needs.actions.return')} className={area} />
            <div>
              <Button variant="outline" disabled={reason.trim().length < 3 || act.isPending} onClick={() => act.mutate({ path: 'return', body: { note: reason } })}>
                {t('needs.actions.returnBtn')}
              </Button>
            </div>
          </div>
        </section>
      )}
      {n.can.cancel && (
        <section className="flex flex-col gap-2 border-t border-border pt-4 first:border-0 first:pt-0" aria-labelledby="need-cancel">
          <h2 id="need-cancel" className="text-sm font-medium">{t('needs.actions.cancel')}</h2>
          <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} maxLength={1000} placeholder={t('needs.actions.cancelHint')} aria-label={t('needs.actions.cancel')} className={area} />
          <div>
            <Button
              variant="outline"
              className="text-danger"
              disabled={reason.trim().length < 3 || act.isPending}
              onClick={async () => {
                if (await confirm({ title: t('needs.actions.cancel'), body: n.title, danger: true, confirmLabel: t('needs.actions.cancelBtn') })) act.mutate({ path: 'cancel', body: { note: reason } })
              }}
            >
              {t('needs.actions.cancelBtn')}
            </Button>
          </div>
        </section>
      )}
      {act.isError && (
        <p role="alert" className="text-sm text-danger">
          {errorText(t, act.error)}
        </p>
      )}
    </Card>
  )
}

function Chat({ needId, canWrite }: { needId: number; canWrite: boolean }) {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const me = useMe().data?.id
  const [text, setText] = useState('')
  const end = useRef<HTMLDivElement>(null)
  const list = useQuery({ queryKey: ['needs', 'comments', needId], queryFn: () => api<NeedComment[]>(`/api/v1/needs/${needId}/comments`), refetchInterval: 8_000 })
  const post = useMutation({
    mutationFn: () => send<NeedComment>('POST', `/api/v1/needs/${needId}/comments`, { body: text }),
    onSuccess: () => {
      setText('')
      void qc.invalidateQueries({ queryKey: ['needs'] })
    },
  })
  useEffect(() => {
    end.current?.scrollIntoView({ block: 'nearest' })
  }, [list.data?.length])
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (text.trim()) post.mutate()
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
          <Button type="submit" disabled={post.isPending || !text.trim()} aria-label={t('tasks.send')}>
            <Send className="size-4" />
          </Button>
        </form>
      )}
      {post.isError && (
        <p role="alert" className="text-sm text-danger">
          {errorText(t, post.error)}
        </p>
      )}
    </Card>
  )
}

function Files({ needId, canWrite }: { needId: number; canWrite: boolean }) {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const confirm = useConfirm()
  const input = useRef<HTMLInputElement>(null)
  const me = useMe().data?.full_name
  const list = useQuery({ queryKey: ['needs', 'files', needId], queryFn: () => api<NeedFile[]>(`/api/v1/needs/${needId}/files`) })
  const refresh = () => void qc.invalidateQueries({ queryKey: ['needs'] })
  const up = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return upload('POST', `/api/v1/needs/${needId}/files`, form)
    },
    onSuccess: refresh,
  })
  const del = useMutation({ mutationFn: (fid: number) => send('DELETE', `/api/v1/needs/${needId}/files/${fid}`), onSuccess: refresh })
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
              <a href={`/api/v1/needs/${needId}/files/${f.id}`} download aria-label={t('tasks.download')}>
                <Button variant="ghost" className="h-8 px-2">
                  <Download className="size-4" />
                </Button>
              </a>
              {f.uploaded_by === me && (
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
