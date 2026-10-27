import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlarmClock, Check, Download, Paperclip, Pencil, Send, Star, Trash2 } from 'lucide-react'
import { useRef, useState, type FormEvent } from 'react'
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
import { sizeText } from '../needs/api'
import { dueText } from '../tasks/api'
import { AssigneePicker } from './Picker'
import { FLOW, PRIORITY_TONE, STATUS_TONE, type Person, type TicketDetail, type TicketFile } from './api'

type Tab = 'chat' | 'files' | 'history'
const area = 'w-full rounded-control border border-border bg-surface px-3 py-2 text-sm'

/** /helpdesk/:id: ticket holati, amallar (sahifa ichida), yozishma, fayl va tarix. */
export function DetailPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const [tab, setTab] = useState<Tab>('chat')
  const q = useQuery({ queryKey: ['helpdesk', 'one', id], queryFn: () => api<TicketDetail>(`/api/v1/helpdesk/${id}`), retry: false, refetchInterval: 15_000 })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const d = q.data
  if (!d) return <Skeleton className="mx-auto h-96 max-w-4xl" />
  const showActions = d.can.take || d.can.assign || d.can.work || d.can.close || d.can.reopen || d.can.cancel

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title={d.title}
        subtitle={`${d.number} · ${d.requester?.name ?? '—'} · ${formatDateTime(d.opened_at, i18n.language)}`}
        backTo="/helpdesk"
        backLabel={t('helpdesk.title')}
        actions={
          <>
            <Link to={`/reminders/new?title=${encodeURIComponent(d.title)}&link=${encodeURIComponent(`/helpdesk/${id}`)}`}>
              <Button variant="outline">
                <AlarmClock className="size-4" />
                {t('reminders.remindMe')}
              </Button>
            </Link>
            {d.can.edit && (
              <Link to={`/helpdesk/${id}/edit`}>
                <Button variant="outline">
                  <Pencil className="size-4" />
                  {t('common.edit')}
                </Button>
              </Link>
            )}
          </>
        }
      />

      <Stepper d={d} />

      <Card className="flex flex-col gap-4 p-6">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={STATUS_TONE[d.status]}>{t(`helpdesk.status.${d.status}`)}</Badge>
          <span className={`rounded-md px-2 py-0.5 text-xs font-medium ${PRIORITY_TONE[d.priority]}`}>{t(`tasks.priority.${d.priority}`)}</span>
          {d.sla_breached && <Badge tone="danger">{t('helpdesk.breached')}</Badge>}
          {d.reopen_count > 0 && <Badge tone="warning">{t('helpdesk.reopenedTimes', { count: d.reopen_count })}</Badge>}
        </div>
        <dl className="grid gap-x-6 gap-y-4 text-sm sm:grid-cols-3">
          <Info label={t('helpdesk.category')}>{d.category?.name ?? '—'}</Info>
          <Info label={t('helpdesk.branch')}>{d.branch?.name ?? '—'}</Info>
          <Info label={t('helpdesk.assignee')}>{d.assignee?.name ?? t('helpdesk.unassigned')}</Info>
          <Info label={t('helpdesk.sla')}>
            <span className={'tabular-nums ' + (d.sla_breached ? 'font-semibold text-danger' : '')}>{d.due_at ? (['new', 'in_progress', 'waiting'].includes(d.status) ? dueText(d.due_at) : formatDateTime(d.due_at, i18n.language)) : '—'}</span>
          </Info>
          <Info label={t('helpdesk.firstResponse')}>{d.first_response_at ? formatDateTime(d.first_response_at, i18n.language) : '—'}</Info>
          {d.device_info && <Info label={t('helpdesk.form.device')}>{d.device_info}</Info>}
          {d.rating !== null && (
            <Info label={t('helpdesk.rating')}>
              <span className="inline-flex" aria-label={`${d.rating}/5`}>
                {[1, 2, 3, 4, 5].map((i) => (
                  <Star key={i} className={'size-4 ' + (i <= (d.rating ?? 0) ? 'fill-warning text-warning' : 'text-border')} />
                ))}
              </span>
            </Info>
          )}
        </dl>
        {d.description && <p className="whitespace-pre-wrap border-t border-border pt-4 text-sm leading-relaxed">{d.description}</p>}
        {d.resolution && (
          <div className="rounded-control bg-surface-2 p-4 text-sm">
            <div className="mb-1 text-xs font-medium text-muted">{t('helpdesk.resolution')}</div>
            <p className="whitespace-pre-wrap">{d.resolution}</p>
          </div>
        )}
        {d.rating_comment && (
          <div className="rounded-control bg-surface-2 p-4 text-sm">
            <div className="mb-1 text-xs font-medium text-muted">{t('helpdesk.ratingComment')}</div>
            <p className="whitespace-pre-wrap">{d.rating_comment}</p>
          </div>
        )}
      </Card>

      <AiSummary entity="ticket" id={id} />
      {showActions && <Actions d={d} />}

      <div className="flex gap-1 border-b border-border" role="tablist">
        {(['chat', 'files', 'history'] as const).map((k) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)} className={'-mb-px border-b-2 px-4 py-2 text-sm font-medium ' + (tab === k ? 'border-primary text-text' : 'border-transparent text-muted hover:text-text')}>
            {t(k === 'chat' ? 'tasks.tabs.comments' : `tasks.tabs.${k}`)}
            {k === 'chat' && d.comments > 0 && <span className="ml-1.5 text-xs text-muted">{d.comments}</span>}
            {k === 'files' && d.files > 0 && <span className="ml-1.5 text-xs text-muted">{d.files}</span>}
          </button>
        ))}
      </div>

      {tab === 'chat' && <Chat d={d} />}
      {tab === 'files' && <Files d={d} />}
      {tab === 'history' && (
        <Card className="p-6">
          <ol className="flex flex-col gap-4 border-l border-border pl-5">
            {d.events
              .filter((e) => e.action !== 'comment')
              .map((e) => (
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

function eventText(t: (k: string, o?: Record<string, unknown>) => string, e: TicketDetail['events'][number]): string {
  const dta = e.data ?? {}
  if (e.action === 'status' && e.to_status) return t('helpdesk.event.status', { status: t(`helpdesk.status.${e.to_status}`) })
  if (e.action === 'assigned' && dta.auto) return t('helpdesk.event.autoAssigned')
  if (e.action === 'assigned' && dta.self) return t('helpdesk.event.taken')
  if (e.action === 'edited' && dta.file_added) return t('helpdesk.event.fileAdded', { name: String(dta.file_added) })
  return t(`helpdesk.event.${e.action}`)
}

/** Holat chizig'i: yangi → jarayonda → hal qilindi → yopildi. */
function Stepper({ d }: { d: TicketDetail }) {
  const { t, i18n } = useTranslation()
  const stage = d.status === 'waiting' ? 'in_progress' : d.status
  const cur = d.status === 'cancelled' ? -1 : FLOW.indexOf(stage as (typeof FLOW)[number])
  const at: Record<string, string | null> = { new: d.opened_at, in_progress: d.first_response_at, resolved: d.resolved_at, closed: d.closed_at }
  return (
    <Card className="p-6">
      <UiStepper
        label={t('helpdesk.stages')}
        current={cur}
        cancelled={d.status === 'cancelled'}
        steps={FLOW.map((s) => ({ key: s, label: s === 'in_progress' && d.status === 'waiting' ? t('helpdesk.status.waiting') : t(`helpdesk.status.${s}`), at: at[s] ? formatDateTime(at[s], i18n.language) : null }))}
      />
      {d.status === 'cancelled' && <p className="mt-4 text-center text-sm text-danger">{t('helpdesk.cancelledHint')}</p>}
    </Card>
  )
}

/** Amallar: olish, tayinlash, kutish/davom, hal qilish, yopish/qayta ochish, bekor qilish. */
function Actions({ d }: { d: TicketDetail }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const confirm = useConfirm()
  const [assignee, setAssignee] = useState<Person | null>(null)
  const [note, setNote] = useState('')
  const [resolution, setResolution] = useState('')
  const [rating, setRating] = useState(0)
  const [reason, setReason] = useState('')
  const done = () => {
    setNote('')
    setResolution('')
    setReason('')
    setRating(0)
    setAssignee(null)
    void qc.invalidateQueries({ queryKey: ['helpdesk'] })
  }
  const act = useMutation({ mutationFn: ({ path, body }: { path: string; body?: unknown }) => send('POST', `/api/v1/helpdesk/${d.id}/${path}`, body ?? {}), onSuccess: done })
  const busy = act.isPending

  return (
    <Card className="flex flex-col gap-6 p-6">
      {d.can.take && (
        <section className="flex flex-wrap items-center gap-3">
          <Button disabled={busy} onClick={() => act.mutate({ path: 'take' })}>
            <Check className="size-4" />
            {t('helpdesk.actions.take')}
          </Button>
          <span className="text-xs text-muted">{t('helpdesk.actions.takeHint')}</span>
        </section>
      )}
      {d.can.assign && (
        <section className="flex flex-col gap-3" aria-labelledby="hd-assign">
          <h2 id="hd-assign" className="font-semibold">{d.assignee ? t('helpdesk.actions.reassign') : t('helpdesk.actions.assign')}</h2>
          <AssigneePicker value={assignee} onChange={setAssignee} />
          <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={1000} placeholder={t('helpdesk.actions.assignNote')} aria-label={t('helpdesk.actions.assignNote')} className={area} />
          <div>
            <Button disabled={!assignee || busy} onClick={() => assignee && act.mutate({ path: 'assign', body: { assignee_id: assignee.id, note: note || null } })}>
              {t('helpdesk.actions.assignBtn')}
            </Button>
          </div>
        </section>
      )}
      {d.can.work && (
        <section className="flex flex-col gap-3" aria-labelledby="hd-resolve">
          <h2 id="hd-resolve" className="font-semibold">{t('helpdesk.actions.resolve')}</h2>
          <textarea value={resolution} onChange={(e) => setResolution(e.target.value)} rows={4} maxLength={10000} placeholder={t('helpdesk.actions.resolveHint')} aria-label={t('helpdesk.resolution')} className={area} />
          <div className="flex flex-wrap gap-2">
            <Button disabled={resolution.trim().length < 3 || busy} onClick={() => act.mutate({ path: 'resolve', body: { resolution } })}>
              <Check className="size-4" />
              {t('helpdesk.actions.resolveBtn')}
            </Button>
          </div>
          <div className="flex flex-col gap-2 border-t border-border pt-4">
            {d.status === 'waiting' ? (
              <div>
                <Button variant="outline" disabled={busy} onClick={() => act.mutate({ path: 'resume' })}>
                  {t('helpdesk.actions.resume')}
                </Button>
              </div>
            ) : (
              <>
                <h3 className="text-sm font-medium">{t('helpdesk.actions.wait')}</h3>
                <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={2000} placeholder={t('helpdesk.actions.waitHint')} aria-label={t('helpdesk.actions.wait')} className={area} />
                <div>
                  <Button variant="outline" disabled={note.trim().length < 3 || busy} onClick={() => act.mutate({ path: 'wait', body: { note } })}>
                    {t('helpdesk.actions.waitBtn')}
                  </Button>
                </div>
              </>
            )}
          </div>
        </section>
      )}
      {d.can.close && (
        <section className="flex flex-col gap-3" aria-labelledby="hd-close">
          <h2 id="hd-close" className="font-semibold">{t('helpdesk.actions.close')}</h2>
          <div className="flex items-center gap-1" role="radiogroup" aria-label={t('helpdesk.rating')}>
            {[1, 2, 3, 4, 5].map((i) => (
              <button key={i} type="button" role="radio" aria-checked={rating === i} aria-label={`${i}`} onClick={() => setRating(rating === i ? 0 : i)}>
                <Star className={'size-6 ' + (i <= rating ? 'fill-warning text-warning' : 'text-border')} />
              </button>
            ))}
          </div>
          <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={1000} placeholder={t('helpdesk.actions.closeNote')} aria-label={t('helpdesk.ratingComment')} className={area} />
          <div>
            <Button disabled={busy} onClick={() => act.mutate({ path: 'close', body: { rating: rating || null, comment: note || null } })}>
              <Check className="size-4" />
              {t('helpdesk.actions.closeBtn')}
            </Button>
          </div>
        </section>
      )}
      {d.can.reopen && (
        <section className="flex flex-col gap-2 border-t border-border pt-4 first:border-0 first:pt-0" aria-labelledby="hd-reopen">
          <h2 id="hd-reopen" className="text-sm font-medium">{t('helpdesk.actions.reopen')}</h2>
          <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} maxLength={2000} placeholder={t('helpdesk.actions.reopenHint')} aria-label={t('helpdesk.actions.reopen')} className={area} />
          <div>
            <Button variant="outline" disabled={reason.trim().length < 3 || busy} onClick={() => act.mutate({ path: 'reopen', body: { note: reason } })}>
              {t('helpdesk.actions.reopenBtn')}
            </Button>
          </div>
        </section>
      )}
      {d.can.cancel && (
        <section className="flex flex-col gap-2 border-t border-border pt-4 first:border-0 first:pt-0" aria-labelledby="hd-cancel">
          <h2 id="hd-cancel" className="text-sm font-medium">{t('helpdesk.actions.cancel')}</h2>
          <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} maxLength={2000} placeholder={t('helpdesk.actions.cancelHint')} aria-label={t('helpdesk.actions.cancel')} className={area} />
          <div>
            <Button
              variant="outline"
              className="text-danger"
              disabled={reason.trim().length < 3 || busy}
              onClick={async () => {
                if (await confirm({ title: t('helpdesk.actions.cancel'), body: d.title, danger: true, confirmLabel: t('helpdesk.actions.cancelBtn') })) act.mutate({ path: 'cancel', body: { note: reason } })
              }}
            >
              {t('helpdesk.actions.cancelBtn')}
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

function Chat({ d }: { d: TicketDetail }) {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const me = useMe().data?.id
  const [text, setText] = useState('')
  const [internal, setInternal] = useState(false)
  const msgs = d.events.filter((e) => e.action === 'comment')
  const post = useMutation({
    mutationFn: () => send('POST', `/api/v1/helpdesk/${d.id}/comments`, { body: text, internal }),
    onSuccess: () => {
      setText('')
      void qc.invalidateQueries({ queryKey: ['helpdesk'] })
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (text.trim()) post.mutate()
  }
  return (
    <Card className="flex flex-col gap-4 p-5">
      <ul className="flex max-h-[28rem] flex-col gap-3 overflow-y-auto" aria-live="polite">
        {msgs.map((c) => {
          const mine = c.actor_id === me
          const hidden = Boolean(c.data?.internal)
          return (
            <li key={c.id} className={'max-w-[85%] rounded-card px-4 py-2.5 text-sm ' + (hidden ? 'self-center border border-dashed border-warning bg-warning/10' : mine ? 'self-end bg-primary text-primary-fg' : 'self-start bg-surface-2')}>
              <div className={'mb-0.5 text-xs ' + (mine && !hidden ? 'text-primary-fg/80' : 'text-muted')}>
                {c.actor} · {formatDateTime(c.created_at, i18n.language)}
                {hidden && ` · ${t('helpdesk.internal')}`}
              </div>
              <p className="whitespace-pre-wrap break-words">{c.note}</p>
            </li>
          )
        })}
        {msgs.length === 0 && <li className="py-6 text-center text-sm text-muted">{t('tasks.noComments')}</li>}
      </ul>
      {d.can.collaborate && (
        <form onSubmit={submit} className="flex flex-col gap-2">
          <div className="flex gap-2">
            <textarea value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && (e.metaKey || e.ctrlKey) && submit(e)} rows={2} maxLength={4000} placeholder={t('tasks.writeComment')} aria-label={t('tasks.writeComment')} className="min-h-11 flex-1 rounded-control border border-border bg-surface px-3 py-2 text-sm" />
            <Button type="submit" disabled={post.isPending || !text.trim()} aria-label={t('tasks.send')}>
              <Send className="size-4" />
            </Button>
          </div>
          {d.can.internal && (
            <label className="flex items-center gap-2 text-xs text-muted">
              <input type="checkbox" className="size-4" checked={internal} onChange={(e) => setInternal(e.target.checked)} />
              {t('helpdesk.internalHint')}
            </label>
          )}
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

function Files({ d }: { d: TicketDetail }) {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const confirm = useConfirm()
  const input = useRef<HTMLInputElement>(null)
  const me = useMe().data?.full_name
  const list = useQuery({ queryKey: ['helpdesk', 'files', d.id], queryFn: () => api<TicketFile[]>(`/api/v1/helpdesk/${d.id}/files`) })
  const refresh = () => void qc.invalidateQueries({ queryKey: ['helpdesk'] })
  const up = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return upload('POST', `/api/v1/helpdesk/${d.id}/files`, form)
    },
    onSuccess: refresh,
  })
  const del = useMutation({ mutationFn: (fid: number) => send('DELETE', `/api/v1/helpdesk/${d.id}/files/${fid}`), onSuccess: refresh })
  return (
    <Card className="flex flex-col gap-4 p-5">
      {d.can.collaborate && (
        <div>
          <input ref={input} type="file" className="sr-only" aria-label={t('tasks.attach')} onChange={(e) => (e.target.files?.[0] && up.mutate(e.target.files[0]), (e.target.value = ''))} />
          <Button variant="outline" disabled={up.isPending} onClick={() => input.current?.click()}>
            <Paperclip className="size-4" />
            {t('tasks.attach')}
          </Button>
          <span className="ml-3 text-xs text-muted">{t('helpdesk.attachHint')}</span>
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
              <a href={`/api/v1/helpdesk/${d.id}/files/${f.id}`} download aria-label={t('tasks.download')}>
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
