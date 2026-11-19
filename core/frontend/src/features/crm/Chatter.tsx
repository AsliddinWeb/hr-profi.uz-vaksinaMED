import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, MessageSquare, StickyNote, Trash2, Zap } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '../../components/ui/Button'
import { Input, Select } from '../../components/ui/Input'
import { useConfirm } from '../../components/ui/confirmContext'
import { api, send } from '../../lib/api'
import { cn } from '../../lib/cn'
import { formatDate, formatDateTime } from '../../lib/format'
import { errorText } from '../auth/errorText'
import { KIND_ICON, KINDS, todayIso, type Feed, type FeedItem, type Kind, type Planned } from './api'
import { ActivityChip } from './parts'

type Tab = 'message' | 'note' | 'activity'

/** O'ng panel «Muhokama»: xabar, ichki eslatma, faoliyat rejalashtirish; rejalashtirilgan faoliyatlar va to'liq tarix. */
export function Chatter({ dealId, canPlan }: { dealId: number; canPlan: boolean }) {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const [tab, setTab] = useState<Tab>('message')
  const feed = useQuery({ queryKey: ['crm', 'feed', dealId], queryFn: () => api<Feed>(`/api/v1/crm/deals/${dealId}/feed`), refetchInterval: 15_000 })
  const refresh = () => void qc.invalidateQueries({ queryKey: ['crm'] })
  const tabs: { k: Tab; icon: typeof MessageSquare }[] = [
    { k: 'message', icon: MessageSquare },
    { k: 'note', icon: StickyNote },
    ...(canPlan ? [{ k: 'activity' as const, icon: Zap }] : []),
  ]
  return (
    <aside aria-label={t('crm.chatter.title')} className="flex flex-col gap-4 rounded-card bg-surface p-4 shadow-card lg:sticky lg:top-4 lg:max-h-[calc(100dvh-2rem)] lg:overflow-y-auto">
      <h2 className="text-[15px] font-semibold">{t('crm.chatter.title')}</h2>
      <div className="flex gap-1 rounded-control bg-surface-2 p-1" role="tablist">
        {tabs.map(({ k, icon: Icon }) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)} className={cn('flex flex-1 items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-medium', tab === k ? 'bg-surface shadow-sm' : 'text-muted hover:text-text')}>
            <Icon className="size-3.5" />
            {t(`crm.chatter.${k}`)}
          </button>
        ))}
      </div>
      {feed.data?.can_write && (tab === 'activity' ? <PlanForm dealId={dealId} onDone={refresh} /> : <Composer dealId={dealId} kind={tab} onDone={refresh} />)}

      <section>
        <h3 className="mb-2 flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-muted">
          {t('crm.chatter.planned')}
          <span className="rounded-full bg-surface-3 px-2 py-0.5 tabular-nums">{feed.data?.planned.length ?? 0}</span>
        </h3>
        <ul className="flex flex-col gap-2">
          {feed.data?.planned.map((a) => <PlannedRow key={a.id} a={a} onDone={refresh} />)}
          {feed.data?.planned.length === 0 && <li className="rounded-control border border-dashed border-border px-3 py-3 text-center text-xs text-muted">{t('crm.chatter.noPlanned')}</li>}
        </ul>
      </section>

      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">{t('crm.chatter.history')}</h3>
        <ol className="flex flex-col gap-3 border-l border-border pl-4">
          {feed.data?.items.map((m) => (
            <li key={m.id} className="relative text-[13px]">
              <span className={cn('absolute -left-[21px] top-1.5 size-2.5 rounded-full', m.kind === 'event' ? 'bg-border-strong' : m.kind === 'note' ? 'bg-(--amber)' : 'bg-primary')} aria-hidden />
              <div className="flex flex-wrap items-baseline justify-between gap-x-2">
                <span className="font-medium">{m.author ?? t('crm.chatter.system')}</span>
                <span className="text-[11px] text-muted">{formatDateTime(m.created_at, i18n.language)}</span>
              </div>
              {m.kind === 'event' ? (
                <p className="text-muted">{eventText(t, m, i18n.language)}</p>
              ) : (
                <p className={cn('mt-1 whitespace-pre-wrap break-words rounded-control px-3 py-2', m.kind === 'note' ? 'bg-(--amber)/10' : 'bg-surface-2')}>
                  {m.kind === 'note' && <span className="mr-1 text-[11px] font-semibold text-(--amber)">{t('crm.chatter.note')}:</span>}
                  {m.body}
                </p>
              )}
            </li>
          ))}
        </ol>
      </section>
    </aside>
  )
}

function Composer({ dealId, kind, onDone }: { dealId: number; kind: 'message' | 'note'; onDone: () => void }) {
  const { t } = useTranslation()
  const [text, setText] = useState('')
  const post = useMutation({
    mutationFn: () => send('POST', `/api/v1/crm/deals/${dealId}/messages`, { kind, body: text }),
    onSuccess: () => (setText(''), onDone()),
  })
  const submit = (e: FormEvent) => (e.preventDefault(), text.trim() && post.mutate())
  return (
    <form onSubmit={submit} className="flex flex-col gap-2">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && (e.ctrlKey || e.metaKey) && submit(e)}
        rows={3}
        maxLength={4000}
        placeholder={t(kind === 'note' ? 'crm.chatter.notePh' : 'crm.chatter.messagePh')}
        aria-label={t(`crm.chatter.${kind}`)}
        className={cn('w-full rounded-control border border-border px-3 py-2 text-[13px]', kind === 'note' ? 'bg-(--amber)/5' : 'bg-surface')}
      />
      <div className="flex items-center justify-between gap-2">
        {post.isError ? <span className="text-xs text-danger">{errorText(t, post.error)}</span> : <span className="text-[11px] text-muted">Ctrl+Enter</span>}
        <Button type="submit" disabled={post.isPending || !text.trim()}>
          {t(kind === 'note' ? 'crm.chatter.saveNote' : 'crm.chatter.send')}
        </Button>
      </div>
    </form>
  )
}

/** Faoliyat rejalashtirish formasi (turi, nomi, sana). */
function PlanForm({ dealId, onDone, initial }: { dealId: number; onDone: () => void; initial?: Partial<{ kind: Kind; title: string }> }) {
  const { t } = useTranslation()
  const [kind, setKind] = useState<Kind>(initial?.kind ?? 'call')
  const [title, setTitle] = useState(initial?.title ?? '')
  const [due, setDue] = useState(todayIso(1))
  const [note, setNote] = useState('')
  const save = useMutation({
    mutationFn: () => send('POST', `/api/v1/crm/deals/${dealId}/activities`, { kind, title: title.trim() || t(`crm.kind.${kind}`), due_date: due, note: note.trim() || null }),
    onSuccess: () => (setTitle(''), setNote(''), onDone()),
  })
  return (
    <form onSubmit={(e) => (e.preventDefault(), save.mutate())} className="flex flex-col gap-2 rounded-control border border-border p-3">
      <div className="grid grid-cols-4 gap-1">
        {KINDS.map((k) => {
          const Icon = KIND_ICON[k]
          return (
            <button key={k} type="button" onClick={() => setKind(k)} aria-pressed={kind === k} className={cn('flex flex-col items-center gap-1 rounded-md px-1 py-1.5 text-[11px]', kind === k ? 'bg-primary/10 text-primary' : 'text-muted hover:bg-surface-2')}>
              <Icon className="size-4" />
              {t(`crm.kind.${k}`)}
            </button>
          )
        })}
      </div>
      <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder={t(`crm.kind.${kind}`)} aria-label={t('crm.chatter.actTitle')} maxLength={200} />
      <div className="flex gap-2">
        <Input type="date" value={due} onChange={(e) => setDue(e.target.value)} aria-label={t('crm.chatter.due')} required className="flex-1" />
        <div className="flex gap-1">
          {[0, 1, 3, 7].map((n) => (
            <button key={n} type="button" onClick={() => setDue(todayIso(n))} className={cn('rounded-md px-2 text-[11px]', due === todayIso(n) ? 'bg-primary/10 text-primary' : 'text-muted hover:bg-surface-2')}>
              {n === 0 ? t('crm.act.today') : `+${n}`}
            </button>
          ))}
        </div>
      </div>
      <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder={t('crm.chatter.actNote')} aria-label={t('crm.chatter.actNote')} maxLength={2000} />
      {save.isError && <p className="text-xs text-danger">{errorText(t, save.error)}</p>}
      <Button type="submit" disabled={save.isPending || !due}>
        {t('crm.chatter.plan')}
      </Button>
    </form>
  )
}

function PlannedRow({ a, onDone }: { a: Planned; onDone: () => void }) {
  const { t, i18n } = useTranslation()
  const confirm = useConfirm()
  const [open, setOpen] = useState(false)
  const [result, setResult] = useState('')
  const [nextKind, setNextKind] = useState<Kind | ''>('')
  const [nextDue, setNextDue] = useState(todayIso(1))
  const Icon = KIND_ICON[a.kind]
  const done = useMutation({
    mutationFn: () =>
      send('POST', `/api/v1/crm/activities/${a.id}/done`, {
        result: result.trim() || null,
        next: nextKind ? { kind: nextKind, title: t(`crm.kind.${nextKind}`), due_date: nextDue } : null,
      }),
    onSuccess: () => (setOpen(false), setResult(''), setNextKind(''), onDone()),
  })
  const cancel = useMutation({ mutationFn: () => send('DELETE', `/api/v1/crm/activities/${a.id}`), onSuccess: onDone })
  return (
    <li className={cn('rounded-control border p-2.5 text-[13px]', a.state === 'overdue' ? 'border-danger/30 bg-danger/5' : 'border-border')}>
      <div className="flex items-start gap-2">
        <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-full bg-surface-2">
          <Icon className="size-3.5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="font-medium">{a.title}</span>
            {a.auto && <span className="rounded bg-primary/10 px-1.5 text-[10px] font-medium text-primary">{t('crm.chatter.auto')}</span>}
          </div>
          <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[11px] text-muted">
            <ActivityChip a={a} />
            <span>{formatDate(a.due_date, i18n.language)}</span>
            {a.assignee?.name && <span>· {a.assignee.name}</span>}
          </div>
          {a.note && <p className="mt-1 text-xs text-muted">{a.note}</p>}
        </div>
      </div>
      {a.can_done && !open && (
        <div className="mt-2 flex gap-1.5">
          <Button variant="success" className="h-7 px-2.5 text-xs" onClick={() => setOpen(true)}>
            <Check className="size-3.5" />
            {t('crm.chatter.markDone')}
          </Button>
          <Button
            variant="ghost"
            className="h-7 px-2 text-xs text-muted"
            aria-label={t('crm.chatter.cancel')}
            onClick={async () => {
              if (await confirm({ title: t('crm.chatter.cancel'), body: a.title, danger: true, confirmLabel: t('crm.chatter.cancel') })) cancel.mutate()
            }}
          >
            <Trash2 className="size-3.5" />
          </Button>
        </div>
      )}
      {open && (
        <form onSubmit={(e) => (e.preventDefault(), done.mutate())} className="mt-2 flex flex-col gap-2 border-t border-border pt-2">
          <Input value={result} onChange={(e) => setResult(e.target.value)} placeholder={t('crm.chatter.resultPh')} aria-label={t('crm.chatter.result')} maxLength={2000} autoFocus />
          <div className="flex gap-2">
            <Select value={nextKind} onChange={(e) => setNextKind(e.target.value as Kind | '')} aria-label={t('crm.chatter.next')} className="flex-1">
              <option value="">{t('crm.chatter.noNext')}</option>
              {KINDS.map((k) => (
                <option key={k} value={k}>
                  {t('crm.chatter.nextKind', { kind: t(`crm.kind.${k}`) })}
                </option>
              ))}
            </Select>
            {nextKind && <Input type="date" value={nextDue} onChange={(e) => setNextDue(e.target.value)} aria-label={t('crm.chatter.due')} className="w-36" />}
          </div>
          {done.isError && <p className="text-xs text-danger">{errorText(t, done.error)}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="ghost" className="h-8 text-xs" onClick={() => setOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" className="h-8 text-xs" disabled={done.isPending}>
              {t('crm.chatter.markDone')}
            </Button>
          </div>
        </form>
      )}
    </li>
  )
}

function eventText(t: (k: string, o?: Record<string, unknown>) => string, m: FeedItem, lang: string): string {
  const d = (m.data ?? {}) as Record<string, unknown>
  const action = String(d.action ?? '')
  if (action === 'stage') return t('crm.ev.stage', { from: d.from, to: d.to, p: d.probability })
  if (action === 'created') return t('crm.ev.created', { stage: d.stage })
  if (action === 'activity_added') return t(d.auto ? 'crm.ev.activityAuto' : 'crm.ev.activityAdded', { title: d.title, due: formatDate(String(d.due), lang) })
  if (action === 'activity_done') return t('crm.ev.activityDone', { title: d.title }) + (d.result ? ` — ${d.result}` : '')
  if (action === 'activity_cancelled') return t('crm.ev.activityCancelled', { title: d.title })
  if (action === 'lost') return t('crm.ev.lost', { reason: d.reason })
  if (action === 'reopened') return t('crm.ev.reopened')
  if (action === 'updated') {
    const f = (d.fields ?? {}) as Record<string, { from: unknown; to: unknown }>
    return Object.entries(f)
      .map(([k, v]) => `${t(`crm.field.${FIELD_KEY[k] ?? k}`, { defaultValue: k })}: ${show(v.from)} → ${show(v.to)}`)
      .join('; ')
  }
  return action
}

const FIELD_KEY: Record<string, string> = { contact_name: 'contact', expected_close: 'expectedClose', owner_id: 'owner' }
const show = (v: unknown) => (v === null || v === undefined || v === '' ? '—' : typeof v === 'number' ? v.toLocaleString('ru-RU') : String(v))
