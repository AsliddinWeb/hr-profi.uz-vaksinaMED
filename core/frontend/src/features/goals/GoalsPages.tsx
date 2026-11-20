import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Lock, Pencil, Plus, Send, Target, Trash2, Undo2, X } from 'lucide-react'
import { useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { UserPicker, type PickedUser } from '../../components/UserPicker'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/EmptyState'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { DeptRanking, GoalTasks, type Task } from './GoalExtras'

type Status = 'draft' | 'pending' | 'approved'
type GoalValues = { title: string; specific: string | null; metric: string; unit: string | null; baseline: number | null; target: number; achievable: string | null; relevant: string | null; deadline: string; owner_user_id: number | null; sort_order: number }
type GoalRow = GoalValues & { id: number; current: number | null; progress: number | null; owner: string | null; tasks: Task[]; task_progress: number | null }
type Change = { id: number; goal_id: number | null; action: 'add' | 'update' | 'remove'; before: GoalValues | null; after: GoalValues | null; reason: string; status: 'pending' | 'approved' | 'rejected'; requested_by: string | null; created_at: string; decided_by: string | null; decision_note: string | null }
type DeptGoals = {
  year: number
  department: { id: number; name: string; yqm: string | null }
  plan: { status: Status; note: string | null; submitted_by: string | null; approved_by: string | null; approved_at: string | null } | null
  goals: GoalRow[]
  changes: Change[]
  can_edit: boolean
  can_approve: boolean
}
type Overview = { year: number; can_approve: boolean; departments: { id: number; name: string; status: Status | null; goals: number; tasks: number; progress: number | null; pending_changes: number }[] }

const BASE = '/api/v1/org/goals'
const TONE = { draft: 'neutral', pending: 'warning', approved: 'success' } as const
const THIS_YEAR = new Date().getFullYear()
const area = 'w-full rounded-control bg-surface px-3 py-2 text-[13px] shadow-[inset_0_0_0_1px_var(--border-strong)] outline-none focus:ring-2 focus:ring-primary/30'

function useYear(): [number, (y: number) => void] {
  const [params, setParams] = useSearchParams()
  const year = Number(params.get('year')) || THIS_YEAR
  return [year, (y) => setParams({ year: String(y) }, { replace: true })]
}

const deptQuery = (deptId: number, year: number) => ({ queryKey: ['goals', 'dept', deptId, year], queryFn: () => api<DeptGoals>(`${BASE}/departments/${deptId}?year=${year}`) })

function YearSelect({ year, onChange }: { year: number; onChange: (y: number) => void }) {
  const now = THIS_YEAR
  return (
    <Select className="w-28" value={year} onChange={(e) => onChange(Number(e.target.value))} aria-label="year">
      {[now - 1, now, now + 1].map((y) => (
        <option key={y} value={y}>
          {y}
        </option>
      ))}
    </Select>
  )
}

function StatusBadge({ status }: { status: Status | null }) {
  const { t } = useTranslation()
  return <Badge tone={status ? TONE[status] : 'neutral'}>{t(`goals.status.${status ?? 'none'}`)}</Badge>
}

function ProgressBar({ value }: { value: number | null }) {
  if (value === null) return <span className="text-xs text-muted">—</span>
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-full min-w-16 overflow-hidden rounded-full bg-surface-2">
        <div className={`h-full rounded-full ${value >= 100 ? 'bg-success' : 'bg-primary'}`} style={{ width: `${Math.min(value, 100)}%` }} />
      </div>
      <span className="w-10 text-right text-xs tabular-nums">{value}%</span>
    </div>
  )
}

const fmt = (n: number | null, unit: string | null) => (n === null ? '—' : `${n.toLocaleString()}${unit ? ` ${unit}` : ''}`)

export function GoalsOverview() {
  const { t } = useTranslation()
  const [year, setYear] = useYear()
  const q = useQuery({ queryKey: ['goals', 'overview', year], queryFn: () => api<Overview>(`${BASE}?year=${year}`) })
  const rows = q.data?.departments ?? []
  const approved = rows.filter((r) => r.status === 'approved').length
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <PageHeader title={t('goals.title')} subtitle={t('goals.overviewSubtitle', { year, approved, total: rows.length })} icon={Target} actions={<YearSelect year={year} onChange={setYear} />} />
      {q.data && <DeptRanking rows={rows} year={year} />}
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs text-muted">
              <tr>
                <th className="px-5 py-2.5 font-medium">{t('org.department')}</th>
                <th className="px-5 py-2.5 font-medium">{t('goals.statusLabel')}</th>
                <th className="px-5 py-2.5 font-medium">{t('goals.count')}</th>
                <th className="px-5 py-2.5 font-medium">{t('stratx.ranking.tasks')}</th>
                <th className="w-48 px-5 py-2.5 font-medium">{t('goals.progress')}</th>
                <th className="px-5 py-2.5 font-medium">{t('goals.pendingChanges')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {q.isLoading && (
                <tr>
                  <td colSpan={6} className="px-5 py-2.5">
                    <Skeleton className="h-24" />
                  </td>
                </tr>
              )}
              {rows.map((r) => (
                <tr key={r.id} className="hover:bg-surface-2">
                  <td className="px-5 py-2.5">
                    <Link to={`/org/goals/${r.id}?year=${year}`} className="font-medium text-primary hover:underline">
                      {r.name}
                    </Link>
                  </td>
                  <td className="px-5 py-2.5">
                    <StatusBadge status={r.status} />
                  </td>
                  <td className="px-5 py-2.5 tabular-nums">{r.goals}</td>
                  <td className="px-5 py-2.5 tabular-nums">{r.tasks}</td>
                  <td className="px-5 py-2.5">
                    <ProgressBar value={r.progress} />
                  </td>
                  <td className="px-5 py-2.5">{r.pending_changes > 0 ? <Badge tone="warning">{r.pending_changes}</Badge> : <span className="text-muted">—</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

export function DeptGoalsCard({ deptId }: { deptId: number }) {
  const { t } = useTranslation()
  const year = THIS_YEAR
  const q = useQuery(deptQuery(deptId, year))
  if (!q.data) return null
  const gs = q.data.goals
  const pr = gs.map((g) => g.progress).filter((x): x is number => x !== null)
  return (
    <Card className="flex flex-col gap-3 p-5">
      <div className="flex items-center gap-2">
        <Target className="size-4 text-primary" />
        <span className="font-medium">{t('goals.cardTitle', { year })}</span>
        <StatusBadge status={q.data.plan?.status ?? null} />
      </div>
      <div className="text-sm text-muted">{gs.length ? t('goals.cardSummary', { n: gs.length }) : t('goals.empty')}</div>
      {pr.length > 0 && <ProgressBar value={Math.round(pr.reduce((a, b) => a + Math.min(b, 100), 0) / pr.length)} />}
      <Link to={`/org/goals/${deptId}?year=${year}`}>
        <Button variant="outline" className="h-8">
          {t('goals.open')}
        </Button>
      </Link>
    </Card>
  )
}

export function DepartmentGoalsPage() {
  const { t } = useTranslation()
  const deptId = Number(useParams().deptId)
  const [year, setYear] = useYear()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const q = useQuery(deptQuery(deptId, year))
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  const run = async (fn: () => Promise<unknown>, ok: string) => {
    setBusy(true)
    try {
      await fn()
      toast.push({ title: ok, tone: 'success' })
      setNote('')
      await qc.invalidateQueries({ queryKey: ['goals'] })
    } catch (e) {
      toast.push({ title: errorText(t, e), tone: 'danger' })
    } finally {
      setBusy(false)
    }
  }

  if (q.isLoading) return <Skeleton className="mx-auto h-96 max-w-5xl" />
  if (!q.data) return <NotFound />
  const { department: dept, plan, goals, changes, can_edit: canEdit, can_approve: canApprove } = q.data
  const status = plan?.status ?? 'draft'
  const draft = status === 'draft'
  const qs = `?year=${year}`
  const action = (path: string, ok: string, body?: unknown) => run(() => send('POST', `${BASE}/departments/${deptId}/${path}${qs}`, body), ok)
  const pendingByGoal = new Set(changes.filter((c) => c.status === 'pending').map((c) => c.goal_id))

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader
        title={dept.name}
        subtitle={t('goals.deptSubtitle', { year })}
        backTo={`/org/goals${qs}`}
        backLabel={t('goals.title')}
        icon={Target}
        actions={
          <>
            <YearSelect year={year} onChange={setYear} />
            {canEdit && (
              <Link to={`/org/goals/${deptId}/new${qs}`}>
                <Button variant={draft ? 'primary' : 'outline'}>
                  <Plus className="size-4" />
                  {t(draft ? 'goals.add' : 'goals.requestAdd')}
                </Button>
              </Link>
            )}
          </>
        }
      />

      <Card className="flex flex-col gap-3 p-5">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={plan?.status ?? null} />
          {status === 'approved' && (
            <span className="inline-flex items-center gap-1 text-sm text-muted">
              <Lock className="size-3.5" />
              {t('goals.lockedHint', { by: plan?.approved_by ?? '—', date: plan?.approved_at ? new Date(plan.approved_at).toLocaleDateString() : '' })}
            </span>
          )}
          {status === 'pending' && <span className="text-sm text-muted">{t('goals.pendingHint', { by: plan?.submitted_by ?? '—' })}</span>}
        </div>
        {dept.yqm && (
          <div className="text-sm">
            <span className="text-muted">{t('goals.yqm')}: </span>
            {dept.yqm}
          </div>
        )}
        {draft && plan?.note && <div className="rounded-lg bg-warning/10 px-3 py-2 text-sm">{t('goals.returnedNote', { note: plan.note })}</div>}
        <div className="flex flex-wrap gap-2">
          {canEdit && draft && goals.length > 0 && (
            <Button disabled={busy} onClick={() => void action('submit', t('goals.submitted'))}>
              <Send className="size-4" />
              {t('goals.submit')}
            </Button>
          )}
          {canApprove && status !== 'approved' && goals.length > 0 && (
            <Button variant="success" disabled={busy} onClick={() => void action('approve', t('goals.approved'))}>
              <Check className="size-4" />
              {t('goals.approve')}
            </Button>
          )}
        </div>
        {canApprove && status === 'pending' && (
          <div className="flex flex-wrap gap-2">
            <Input className="max-w-md" value={note} onChange={(e) => setNote(e.target.value)} placeholder={t('goals.returnReason')} aria-label={t('goals.returnReason')} maxLength={2000} />
            <Button variant="outline" disabled={busy || !note.trim()} onClick={() => void action('return', t('goals.returned'), { note })}>
              <Undo2 className="size-4" />
              {t('goals.return')}
            </Button>
          </div>
        )}
      </Card>

      {goals.length === 0 && <EmptyState icon={Target} title={t('goals.empty')} hint={t('goals.emptyHint')} />}
      {goals.map((g, i) => (
        <GoalCard
          key={g.id}
          n={i + 1}
          g={g}
          actions={
            <>
              {canEdit && draft && (
                <>
                  <Link to={`/org/goals/${deptId}/items/${g.id}/edit${qs}`}>
                    <Button variant="outline" className="h-8">
                      <Pencil className="size-4" />
                      {t('common.edit')}
                    </Button>
                  </Link>
                  <Button
                    variant="outline"
                    className="h-8 text-danger"
                    disabled={busy}
                    onClick={async () => {
                      if (await confirm({ title: t('common.delete'), body: g.title, danger: true, confirmLabel: t('common.delete') })) void run(() => send('DELETE', `${BASE}/items/${g.id}`), t('org.deleted'))
                    }}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </>
              )}
              {canEdit && status === 'approved' && (pendingByGoal.has(g.id) ? <Badge tone="warning">{t('goals.changePending')}</Badge> : (
                <>
                  <Link to={`/org/goals/${deptId}/items/${g.id}/edit${qs}`}>
                    <Button variant="outline" className="h-8">
                      <Pencil className="size-4" />
                      {t('goals.requestChange')}
                    </Button>
                  </Link>
                  <Link to={`/org/goals/${deptId}/items/${g.id}/edit${qs}&mode=remove`}>
                    <Button variant="outline" className="h-8 text-danger">
                      <Trash2 className="size-4" />
                      {t('goals.requestRemove')}
                    </Button>
                  </Link>
                </>
              ))}
            </>
          }
          progressEditor={canEdit && status === 'approved' ? <ProgressEditor g={g} onSave={(v) => run(() => send('PUT', `${BASE}/items/${g.id}/progress`, { current: v }), t('common.saved'))} busy={busy} /> : null}
          tasks={<GoalTasks goalId={g.id} tasks={g.tasks} canEdit={canEdit} />}
        />
      ))}

      {changes.length > 0 && (
        <Card className="flex flex-col gap-3 p-5">
          <div className="font-medium">{t('goals.changesTitle')}</div>
          {changes.map((c) => (
            <ChangeRow key={c.id} c={c} canApprove={canApprove} busy={busy} onDecide={(approve, n) => run(() => send('POST', `${BASE}/changes/${c.id}/decide`, { approve, note: n || null }), t(approve ? 'goals.changeApproved' : 'goals.changeRejected'))} />
          ))}
        </Card>
      )}
    </div>
  )
}

function GoalCard({ n, g, actions, progressEditor, tasks }: { n: number; g: GoalRow; actions: ReactNode; progressEditor: ReactNode; tasks?: ReactNode }) {
  const { t } = useTranslation()
  const row = (k: string, v: ReactNode) =>
    v ? (
      <div className="grid gap-1 text-sm sm:grid-cols-[9rem_1fr]">
        <span className="text-muted">{t(`goals.f.${k}`)}</span>
        <span>{v}</span>
      </div>
    ) : null
  return (
    <Card className="flex flex-col gap-3 p-5">
      <div className="flex flex-wrap items-start gap-2">
        <div className="flex-1 text-[15px] font-semibold">
          {n}. {g.title}
        </div>
        <div className="flex flex-wrap gap-2">{actions}</div>
      </div>
      {row('specific', g.specific)}
      {row('metric', `${g.metric}: ${fmt(g.baseline, g.unit)} → ${fmt(g.target, g.unit)}`)}
      {row('achievable', g.achievable)}
      {row('relevant', g.relevant)}
      {row('deadline', new Date(g.deadline).toLocaleDateString())}
      {row('owner', g.owner)}
      <div className="grid items-center gap-2 text-sm sm:grid-cols-[9rem_1fr]">
        <span className="text-muted">{t('goals.progress')}</span>
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-3">
            <span className="whitespace-nowrap">{fmt(g.current, g.unit)}</span>
            <div className="flex-1">
              <ProgressBar value={g.progress} />
            </div>
          </div>
          {g.task_progress !== null && <span className="text-xs text-muted">{t('stratx.tasks.avg', { p: g.task_progress })}</span>}
          {progressEditor}
        </div>
      </div>
      {tasks}
    </Card>
  )
}

function ProgressEditor({ g, onSave, busy }: { g: GoalRow; onSave: (v: number | null) => void; busy: boolean }) {
  const { t } = useTranslation()
  const [v, setV] = useState(g.current?.toString() ?? '')
  return (
    <div className="flex gap-2">
      <Input className="max-w-40" type="number" step="any" value={v} onChange={(e) => setV(e.target.value)} placeholder={t('goals.currentValue')} aria-label={t('goals.currentValue')} />
      <Button variant="outline" className="h-9" disabled={busy || v === (g.current?.toString() ?? '')} onClick={() => onSave(v === '' ? null : Number(v))}>
        {t('goals.updateProgress')}
      </Button>
    </div>
  )
}

function ChangeRow({ c, canApprove, busy, onDecide }: { c: Change; canApprove: boolean; busy: boolean; onDecide: (approve: boolean, note: string) => void }) {
  const { t } = useTranslation()
  const [note, setNote] = useState('')
  const diff = c.action === 'update' && c.before && c.after ? (Object.keys(c.after) as (keyof GoalValues)[]).filter((k) => k !== 'sort_order' && c.before![k] !== c.after![k]) : []
  return (
    <div className="flex flex-col gap-2 rounded-xl bg-surface-2 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="info">{t(`goals.action.${c.action}`)}</Badge>
        <span className="font-medium">{(c.after ?? c.before)?.title}</span>
        <Badge tone={c.status === 'approved' ? 'success' : c.status === 'rejected' ? 'danger' : 'warning'}>{t(`goals.changeStatus.${c.status}`)}</Badge>
        <span className="ml-auto text-xs text-muted">
          {c.requested_by} · {new Date(c.created_at).toLocaleDateString()}
        </span>
      </div>
      <div>
        <span className="text-muted">{t('goals.reason')}: </span>
        {c.reason}
      </div>
      {diff.map((k) => (
        <div key={k} className="text-xs">
          <span className="text-muted">{t(`goals.f.${k === 'owner_user_id' ? 'owner' : k}`)}: </span>
          <s className="text-muted">{String(c.before![k] ?? '—')}</s> → <b>{String(c.after![k] ?? '—')}</b>
        </div>
      ))}
      {c.decided_by && (
        <div className="text-xs text-muted">
          {t('goals.decidedBy', { by: c.decided_by })}
          {c.decision_note ? `: ${c.decision_note}` : ''}
        </div>
      )}
      {canApprove && c.status === 'pending' && (
        <div className="flex flex-wrap gap-2">
          <Input className="max-w-sm" value={note} onChange={(e) => setNote(e.target.value)} placeholder={t('goals.decisionNote')} aria-label={t('goals.decisionNote')} maxLength={2000} />
          <Button variant="success" className="h-9" disabled={busy} onClick={() => onDecide(true, note)}>
            <Check className="size-4" />
            {t('goals.approve')}
          </Button>
          <Button variant="outline" className="h-9 text-danger" disabled={busy} onClick={() => onDecide(false, note)}>
            <X className="size-4" />
            {t('goals.reject')}
          </Button>
        </div>
      )}
    </div>
  )
}

export function GoalFormPage() {
  const { deptId, goalId } = useParams()
  const [year] = useYear()
  const q = useQuery(deptQuery(Number(deptId), year))
  if (q.isLoading) return <Skeleton className="mx-auto h-96 max-w-5xl" />
  const goal = goalId ? q.data?.goals.find((g) => g.id === Number(goalId)) : undefined
  if (!q.data || (goalId && !goal)) return <NotFound />
  return <GoalForm key={goalId ?? 'new'} data={q.data} goal={goal ?? null} year={year} />
}

function GoalForm({ data, goal, year }: { data: DeptGoals; goal: GoalRow | null; year: number }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [params] = useSearchParams()
  const locked = (data.plan?.status ?? 'draft') !== 'draft'
  const remove = locked && params.get('mode') === 'remove'
  const back = `/org/goals/${data.department.id}?year=${year}`
  const [v, setV] = useState({
    title: goal?.title ?? '',
    specific: goal?.specific ?? '',
    metric: goal?.metric ?? '',
    unit: goal?.unit ?? '',
    baseline: goal?.baseline?.toString() ?? '',
    target: goal?.target?.toString() ?? '',
    achievable: goal?.achievable ?? '',
    relevant: goal?.relevant ?? '',
    deadline: goal?.deadline ?? `${year}-12-31`,
  })
  const [owner, setOwner] = useState<PickedUser | null>(goal?.owner_user_id ? { id: goal.owner_user_id, name: goal.owner ?? '' } : null)
  const [reason, setReason] = useState('')
  const set = (k: keyof typeof v) => (e: { target: { value: string } }) => setV((s) => ({ ...s, [k]: e.target.value }))

  const save = useMutation({
    mutationFn: () => {
      const values = {
        ...v,
        specific: v.specific.trim() || null,
        unit: v.unit.trim() || null,
        achievable: v.achievable.trim() || null,
        relevant: v.relevant.trim() || null,
        baseline: v.baseline === '' ? null : Number(v.baseline),
        target: Number(v.target),
        owner_user_id: owner?.id ?? null,
        sort_order: goal?.sort_order ?? data.goals.length,
      }
      if (locked) {
        const body = remove ? { action: 'remove', goal_id: goal?.id, reason } : { action: goal ? 'update' : 'add', goal_id: goal?.id ?? null, values, reason }
        return send('POST', `${BASE}/departments/${data.department.id}/changes?year=${year}`, body)
      }
      return goal ? send('PUT', `${BASE}/items/${goal.id}`, values) : send('POST', `${BASE}/departments/${data.department.id}?year=${year}`, values)
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['goals'] })
      toast.push({ title: t(locked ? 'goals.changeRequested' : 'common.saved'), tone: 'success' })
      navigate(back)
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  const text = (k: keyof typeof v, rows = 2) => (id: string) => <textarea id={id} rows={rows} maxLength={2000} value={v[k]} onChange={set(k)} disabled={remove} className={area} />
  const title = remove ? t('goals.requestRemove') : locked ? t(goal ? 'goals.requestChange' : 'goals.requestAdd') : t(goal ? 'goals.edit' : 'goals.add')

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={title} subtitle={`${data.department.name} · ${year}`} backTo={back} backLabel={data.department.name} icon={Target} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        {locked && (
          <FormSection title={t('goals.reason')} description={t('goals.reasonHint')}>
            <Field label={t('goals.reason')}>{(id) => <textarea id={id} rows={3} required minLength={3} maxLength={2000} value={reason} onChange={(e) => setReason(e.target.value)} className={area} autoFocus />}</Field>
          </FormSection>
        )}
        <FormSection title={t('goals.s.title')} description={t('goals.s.hint')}>
          <Field label={t('goals.f.title')}>{(id) => <Input id={id} value={v.title} onChange={set('title')} required maxLength={200} disabled={remove} autoFocus={!locked} />}</Field>
          <Field label={t('goals.f.specific')}>{text('specific', 3)}</Field>
        </FormSection>
        <FormSection title={t('goals.m.title')} description={t('goals.m.hint')}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('goals.f.metricName')}>{(id) => <Input id={id} value={v.metric} onChange={set('metric')} required maxLength={120} disabled={remove} />}</Field>
            <Field label={t('goals.f.unit')}>{(id) => <Input id={id} value={v.unit} onChange={set('unit')} maxLength={20} disabled={remove} />}</Field>
            <Field label={t('goals.f.baseline')}>{(id) => <Input id={id} type="number" step="any" value={v.baseline} onChange={set('baseline')} disabled={remove} />}</Field>
            <Field label={t('goals.f.target')}>{(id) => <Input id={id} type="number" step="any" value={v.target} onChange={set('target')} required disabled={remove} />}</Field>
          </div>
        </FormSection>
        <FormSection title={t('goals.ar.title')} description={t('goals.ar.hint')}>
          <Field label={t('goals.f.achievable')}>{text('achievable')}</Field>
          <Field label={t('goals.f.relevant')}>{text('relevant')}</Field>
        </FormSection>
        <FormSection title={t('goals.t.title')} description={t('goals.t.hint', { year })}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('goals.f.deadline')}>{(id) => <Input id={id} type="date" min={`${year}-01-01`} max={`${year}-12-31`} value={v.deadline} onChange={set('deadline')} required disabled={remove} />}</Field>
            <Field label={t('goals.f.owner')}>{(id) => <UserPicker id={id} value={owner} onChange={setOwner} />}</Field>
          </div>
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Link to={back}>
            <Button variant="ghost">{t('common.cancel')}</Button>
          </Link>
          <Button type="submit" variant={remove ? 'danger' : 'primary'} disabled={save.isPending}>
            {locked ? t('goals.sendRequest') : t('common.save')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
