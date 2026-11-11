import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarDays, ChevronLeft, ChevronRight, ClipboardCheck, Plus, Search, Store } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'

import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Field, Input, Select } from '../../components/ui/Input'
import { Tabs } from '../../components/ui/Tabs'
import { api, send } from '../../lib/api'
import { useCan } from '../auth/useAuth'
import { errorText } from '../auth/errorText'

type Task = {
  id: number
  branch: { id: number; name: string }
  kind: string
  status: string
  planned_date: string
  note: string | null
  result_note: string | null
  shortage_amount: number | null
  score: number | null
  revizor: { id: number; name: string } | null
  decision_note: string | null
}
type BranchRow = { id: number; name: string; manager: string | null; coordinator: string | null; last_done: string | null; next_due: string | null; days_left: number | null; status: string; open_task: { id: number; status: string; planned_date: string; revizor: string | null } | null }
type TabKey = 'branches' | 'tasks' | 'calendar'

const STATUS_COLOR: Record<string, string> = { overdue: 'var(--c-rose)', cycle_done: 'var(--c-teal)', soon: 'var(--c-amber)', in_progress: 'var(--c-blue)', on_plan: 'var(--c-green)', never: 'var(--c-slate)' }
const TASK_COLOR: Record<string, string> = { assigned: 'var(--c-slate)', accepted: 'var(--c-violet)', in_progress: 'var(--c-blue)', review: 'var(--c-amber)', done: 'var(--c-green)', cancelled: 'var(--c-rose)' }
const fmt = (d: string | null) => (d ? d.split('-').reverse().join('.') : '—')

/** /revisions — Reviziya bo'limi: filial sikli, revizor vazifalari va oylik kalendar. */
export function RevisionsPage() {
  const { t } = useTranslation()
  const can = useCan()
  const [sp, setSp] = useSearchParams()
  const tab = (sp.get('tab') as TabKey) || 'branches'
  const manage = can('revision.manage')
  const [creating, setCreating] = useState<number | null | undefined>(undefined)

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <section className="rounded-[22px] bg-[linear-gradient(120deg,#0f2a4a_0%,#16325c_100%)] p-6 text-white shadow-card">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-white/60">{t('rev.kicker')}</div>
        <h1 className="mt-1 text-2xl font-semibold">{t('rev.title')}</h1>
        <p className="mt-1 max-w-2xl text-sm text-white/75">{t('rev.subtitle')}</p>
      </section>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs<TabKey>
          value={tab}
          onChange={(k) => setSp({ tab: k })}
          items={[
            { key: 'branches', label: t('rev.tab.branches') },
            { key: 'tasks', label: t('rev.tab.tasks') },
            { key: 'calendar', label: t('rev.tab.calendar') },
          ]}
        />
        {manage && (
          <Button onClick={() => setCreating(null)}>
            <Plus className="size-4" />
            {t('rev.assign')}
          </Button>
        )}
      </div>
      {creating !== undefined && <AssignForm branchId={creating} onClose={() => setCreating(undefined)} />}
      {tab === 'branches' && <Branches onAssign={manage ? (id) => setCreating(id) : undefined} />}
      {tab === 'tasks' && <Tasks />}
      {tab === 'calendar' && <Calendar />}
    </div>
  )
}

function Branches({ onAssign }: { onAssign?: (id: number) => void }) {
  const { t } = useTranslation()
  const [q, setQ] = useState('')
  const [status, setStatus] = useState<string>('')
  const d = useQuery({ queryKey: ['revisions', 'branches'], queryFn: () => api<{ cycle_days: number; counts: Record<string, number>; items: BranchRow[] }>('/api/v1/revisions/branches') })
  const items = (d.data?.items ?? []).filter((b) => (!status || b.status === status) && (!q || `${b.name} ${b.manager ?? ''} ${b.coordinator ?? ''} ${b.open_task?.revizor ?? ''}`.toLowerCase().includes(q.toLowerCase())))
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {Object.keys(STATUS_COLOR).map((k) => (
          <button key={k} type="button" onClick={() => setStatus(status === k || k === 'cycle_done' ? '' : k)} style={{ ['--gc' as string]: STATUS_COLOR[k] }}
            className={`rounded-card border p-3 text-left transition-colors ${status === k ? 'border-(--gc) bg-[color-mix(in_oklab,var(--gc)_10%,transparent)]' : 'border-border bg-surface'}`}>
            <div className="font-mono text-2xl font-semibold text-(--gc)">{d.data?.counts[k] ?? 0}</div>
            <div className="text-[13px] font-medium">{t(`rev.st.${k}`)}</div>
            <div className="text-[11px] text-muted">{t(`rev.stHint.${k}`)}</div>
          </button>
        ))}
      </div>
      <div className="relative">
        <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
        <Input className="pl-9" placeholder={t('rev.search')} value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <Card className="divide-y divide-border">
        {items.length === 0 && <p className="p-8 text-center text-sm text-muted">{t('rev.empty')}</p>}
        {items.map((b) => (
          <div key={b.id} className="flex flex-wrap items-center gap-3 p-3.5">
            <Store className="size-5 text-muted" />
            <div className="min-w-48 flex-1">
              <div className="font-medium">{b.name}</div>
              <div className="text-xs text-muted">
                {t('rev.manager')}: {b.manager ?? '—'} · {t('rev.coordinator')}: {b.coordinator ?? '—'}
              </div>
            </div>
            <div className="text-xs text-muted">
              <div>{t('rev.lastDone')}: <b className="text-fg">{fmt(b.last_done)}</b></div>
              <div>{t('rev.nextDue')}: <b className="text-fg">{fmt(b.next_due)}</b>{b.days_left != null && ` (${b.days_left} ${t('rev.days')})`}</div>
            </div>
            {b.open_task && <span className="text-xs text-muted">{t(`rev.task.${b.open_task.status}`)} · {b.open_task.revizor ?? '—'} · {fmt(b.open_task.planned_date)}</span>}
            <span className="rounded-full px-2.5 py-1 text-xs font-semibold text-white" style={{ background: STATUS_COLOR[b.status] }}>{t(`rev.st.${b.status}`)}</span>
            {onAssign && !b.open_task && (
              <Button variant="outline" onClick={() => onAssign(b.id)}>
                {t('rev.assign')}
              </Button>
            )}
          </div>
        ))}
      </Card>
    </div>
  )
}

function Tasks() {
  const { t } = useTranslation()
  const d = useQuery({ queryKey: ['revisions', 'tasks'], queryFn: () => api<{ counts: Record<string, number> } & Record<'review' | 'overdue' | 'today' | 'future', Task[]>>('/api/v1/revisions/tasks') })
  const groups = ['review', 'overdue', 'today', 'future'] as const
  const all = groups.flatMap((g) => d.data?.[g] ?? [])
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {groups.map((g) => (
          <Card key={g} className="p-3">
            <div className="font-mono text-2xl font-semibold">{d.data?.counts[g] ?? 0}</div>
            <div className="text-[13px] font-medium">{t(`rev.grp.${g}`)}</div>
            <div className="text-[11px] text-muted">{t(`rev.grpHint.${g}`)}</div>
          </Card>
        ))}
      </div>
      {all.length === 0 ? (
        <Card className="p-8 text-center">
          <ClipboardCheck className="mx-auto size-8 text-muted" />
          <p className="mt-2 font-medium">{t('rev.noTasks')}</p>
          <p className="text-sm text-muted">{t('rev.noTasksHint')}</p>
        </Card>
      ) : (
        all.map((x) => <TaskCard key={x.id} task={x} />)
      )}
    </div>
  )
}

function TaskCard({ task }: { task: Task }) {
  const { t } = useTranslation()
  const can = useCan()
  const qc = useQueryClient()
  const [note, setNote] = useState('')
  const [shortage, setShortage] = useState('')
  const [score, setScore] = useState('')
  const act = useMutation({
    mutationFn: ({ action, body }: { action: string; body?: unknown }) => send('POST', `/api/v1/revisions/tasks/${task.id}/${action}`, body ?? {}),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['revisions'] }),
  })
  const manage = can('revision.manage')
  return (
    <Card className="flex flex-col gap-3 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold">{task.branch.name}</span>
        <span className="rounded-full px-2 py-0.5 text-[11px] font-semibold text-white" style={{ background: TASK_COLOR[task.status] }}>{t(`rev.task.${task.status}`)}</span>
        <span className="text-xs text-muted">{t(`rev.kind.${task.kind}`)} · {fmt(task.planned_date)} · {task.revizor?.name ?? '—'}</span>
      </div>
      {task.note && <p className="text-sm text-muted">{task.note}</p>}
      {task.status === 'review' && (
        <div className="rounded-lg bg-surface-2 p-3 text-sm">
          <div>{t('rev.shortage')}: <b>{task.shortage_amount != null ? task.shortage_amount.toLocaleString('ru-RU') : '—'}</b> · {t('rev.score')}: <b>{task.score ?? '—'}</b></div>
          {task.result_note && <p className="mt-1">{task.result_note}</p>}
        </div>
      )}
      {['accepted', 'in_progress'].includes(task.status) && (
        <div className="grid gap-2 md:grid-cols-[1fr_10rem_8rem]">
          <Input placeholder={t('rev.resultNote')} value={note} onChange={(e) => setNote(e.target.value)} />
          <Input type="number" min={0} placeholder={t('rev.shortage')} value={shortage} onChange={(e) => setShortage(e.target.value)} />
          <Input type="number" min={0} max={100} placeholder={t('rev.score')} value={score} onChange={(e) => setScore(e.target.value)} />
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {task.status === 'assigned' && <Button variant="outline" disabled={act.isPending} onClick={() => act.mutate({ action: 'accept' })}>{t('rev.act.accept')}</Button>}
        {['assigned', 'accepted'].includes(task.status) && <Button disabled={act.isPending} onClick={() => act.mutate({ action: 'start' })}>{t('rev.act.start')}</Button>}
        {['accepted', 'in_progress'].includes(task.status) && (
          <Button disabled={act.isPending} onClick={() => act.mutate({ action: 'submit', body: { result_note: note || null, shortage_amount: shortage ? Number(shortage) : null, score: score ? Number(score) : null } })}>
            {t('rev.act.submit')}
          </Button>
        )}
        {manage && task.status === 'review' && (
          <>
            <Button variant="success" disabled={act.isPending} onClick={() => act.mutate({ action: 'approve' })}>{t('rev.act.approve')}</Button>
            <Button variant="warning" disabled={act.isPending} onClick={() => act.mutate({ action: 'return' })}>{t('rev.act.return')}</Button>
          </>
        )}
        {manage && <Button variant="ghost" disabled={act.isPending} onClick={() => act.mutate({ action: 'cancel' })}>{t('rev.act.cancel')}</Button>}
      </div>
      {act.isError && <p role="alert" className="text-sm text-danger">{errorText(t, act.error)}</p>}
    </Card>
  )
}

function Calendar() {
  const { t } = useTranslation()
  const [cursor, setCursor] = useState(() => new Date(new Date().getFullYear(), new Date().getMonth(), 1))
  const [day, setDay] = useState(() => new Date().toISOString().slice(0, 10))
  const month = `${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, '0')}`
  const d = useQuery({ queryKey: ['revisions', 'calendar', month], queryFn: () => api<{ items: Task[] }>(`/api/v1/revisions/calendar?month=${month}`) })
  const items = d.data?.items ?? []
  const first = (cursor.getDay() + 6) % 7
  const days = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0).getDate()
  const cells = [...Array(first).fill(null), ...Array.from({ length: days }, (_, i) => i + 1)]
  const iso = (n: number) => `${month}-${String(n).padStart(2, '0')}`
  const sel = items.filter((x) => x.planned_date === day)
  return (
    <Card className="flex flex-col gap-4 p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Button variant="ghost" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))} aria-label="prev"><ChevronLeft className="size-4" /></Button>
          <b className="flex items-center gap-2"><CalendarDays className="size-4" />{month}</b>
          <Button variant="ghost" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))} aria-label="next"><ChevronRight className="size-4" /></Button>
        </div>
        <span className="text-sm text-muted">{t('rev.planned', { n: items.length })}</span>
      </div>
      <div className="grid grid-cols-7 gap-1 text-center text-xs">
        {['DU', 'SE', 'CH', 'PA', 'JU', 'SH', 'YA'].map((w) => <div key={w} className="py-1 font-semibold text-muted">{w}</div>)}
        {cells.map((n, i) => {
          if (!n) return <div key={`e${i}`} />
          const list = items.filter((x) => x.planned_date === iso(n))
          return (
            <button key={n} type="button" onClick={() => setDay(iso(n))} className={`flex min-h-14 flex-col items-center gap-1 rounded-lg border p-1 ${day === iso(n) ? 'border-primary' : 'border-border'}`}>
              <span>{n}</span>
              <span className="flex flex-wrap justify-center gap-0.5">{list.map((x) => <i key={x.id} className="size-1.5 rounded-full" style={{ background: TASK_COLOR[x.status] }} />)}</span>
            </button>
          )
        })}
      </div>
      <div className="flex flex-wrap gap-3 text-[11px] text-muted">
        {Object.keys(TASK_COLOR).map((k) => <span key={k} className="flex items-center gap-1"><i className="size-2 rounded-full" style={{ background: TASK_COLOR[k] }} />{t(`rev.task.${k}`)}</span>)}
      </div>
      <div>
        <div className="mb-2 text-sm font-semibold">{fmt(day)}</div>
        {sel.length === 0 ? <p className="text-sm text-muted">{t('rev.noDay')}</p> : sel.map((x) => <div key={x.id} className="text-sm">{x.branch.name} · {t(`rev.task.${x.status}`)} · {x.revizor?.name ?? '—'}</div>)}
      </div>
    </Card>
  )
}

function AssignForm({ branchId, onClose }: { branchId: number | null; onClose: () => void }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const branches = useQuery({ queryKey: ['revisions', 'branches'], queryFn: () => api<{ items: BranchRow[] }>('/api/v1/revisions/branches') })
  const revizors = useQuery({ queryKey: ['revisions', 'revizors'], queryFn: () => api<{ id: number; name: string }[]>('/api/v1/revisions/revizors') })
  const [form, setForm] = useState({ branch_id: branchId ?? 0, revizor_user_id: 0, planned_date: new Date().toISOString().slice(0, 10), kind: 'cycle', note: '' })
  const save = useMutation({
    mutationFn: () => send('POST', '/api/v1/revisions/tasks', { ...form, note: form.note || null }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['revisions'] })
      onClose()
    },
  })
  return (
    <Card className="grid gap-3 p-4 md:grid-cols-2">
      <Field label={t('rev.f.branch')}>{(id) => (
        <Select id={id} value={form.branch_id} onChange={(e) => setForm({ ...form, branch_id: Number(e.target.value) })}>
          <option value={0}>—</option>
          {branches.data?.items.filter((b) => !b.open_task).map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
        </Select>
      )}</Field>
      <Field label={t('rev.f.revizor')}>{(id) => (
        <Select id={id} value={form.revizor_user_id} onChange={(e) => setForm({ ...form, revizor_user_id: Number(e.target.value) })}>
          <option value={0}>—</option>
          {revizors.data?.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
        </Select>
      )}</Field>
      <Field label={t('rev.f.date')}>{(id) => <Input id={id} type="date" value={form.planned_date} onChange={(e) => setForm({ ...form, planned_date: e.target.value })} />}</Field>
      <Field label={t('rev.f.kind')}>{(id) => (
        <Select id={id} value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
          {['cycle', 'shortage', 'inventory', 'check'].map((k) => <option key={k} value={k}>{t(`rev.kind.${k}`)}</option>)}
        </Select>
      )}</Field>
      <div className="md:col-span-2">
        <Field label={t('rev.f.note')}>{(id) => <Input id={id} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />}</Field>
      </div>
      {save.isError && <p role="alert" className="text-sm text-danger md:col-span-2">{errorText(t, save.error)}</p>}
      <div className="flex gap-2 md:col-span-2">
        <Button disabled={!form.branch_id || !form.revizor_user_id || save.isPending} onClick={() => save.mutate()}>{t('rev.assign')}</Button>
        <Button variant="outline" onClick={onClose}>{t('common.cancel')}</Button>
      </div>
    </Card>
  )
}
