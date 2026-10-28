import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowDown, ArrowUp, Check, Plus, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'

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
import { formatDateTime } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { todayLocal } from '../attendance/api'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import { usePositionOptions } from '../org/usePositionOptions'
import { STATUS_TONE, type DutyControl, type DutyItem, type DutyStatus, type DutyTemplate, type MyDuty } from './api'

const LIST = '/checklists/duty'
const area = 'w-full rounded-control border border-border bg-surface px-3 py-2 text-sm'

/** /checklists/duty: bo'lim va lavozim ish chek-listlari. */
export function DutyTemplatesPage() {
  const { t } = useTranslation()
  const can = useCan()
  const list = useQuery({ queryKey: ['duty', 'templates'], queryFn: () => api<DutyTemplate[]>('/api/v1/duty/templates') })
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title={t('duty.title')}
        subtitle={t('duty.subtitle')}
        actions={
          can('duty.manage') && (
            <Link to={`${LIST}/new`}>
              <Button>
                <Plus className="size-4" />
                {t('duty.add')}
              </Button>
            </Link>
          )
        }
      />
      {!list.data ? (
        <Skeleton className="h-40" />
      ) : (
        <div className="flex flex-col gap-3">
          {list.data.map((c) => (
            <Link key={c.id} to={`${LIST}/${c.id}/edit`}>
              <Card className="flex flex-wrap items-center justify-between gap-3 p-4 hover:bg-surface-2">
                <div>
                  <div className="font-medium">{c.name}</div>
                  <div className="text-sm text-muted">
                    {c.scope === 'position' ? `${t('duty.scope.position')}: ${c.position ?? '—'}` : `${t('duty.scope.department')}: ${c.department ?? '—'}`} · {t(`duty.freq.${c.frequency}`)} · {t('duty.until', { time: c.deadline_time })} · {t('duty.points', { n: c.item_count })}
                  </div>
                </div>
                {!c.is_active && <Badge>{t('duty.inactive')}</Badge>}
              </Card>
            </Link>
          ))}
          {list.data.length === 0 && <Card className="p-8 text-center text-muted">{t('duty.empty')}</Card>}
        </div>
      )}
    </div>
  )
}

/** /checklists/duty/new (?department=ID | ?position=ID) va /checklists/duty/:id/edit */
export function DutyFormPage() {
  const { id } = useParams()
  const cid = id ? Number(id) : null
  const q = useQuery({ queryKey: ['duty', 'template', cid], queryFn: () => api<DutyTemplate>(`/api/v1/duty/templates/${cid}`), enabled: cid !== null, retry: false })
  if (cid === null) return <DutyForm tpl={null} />
  if (q.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  return q.data ? <DutyForm key={q.data.id} tpl={q.data} /> : null
}

function DutyForm({ tpl }: { tpl: DutyTemplate | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const can = useCan()
  const [params] = useSearchParams()
  const positions = usePositionOptions()
  const departments = useQuery({ queryKey: ['org', 'departments-names'], queryFn: () => api<{ id: number; name: string }[]>('/api/v1/org/departments') })
  const preDept = Number(params.get('department')) || null
  const prePos = Number(params.get('position')) || null
  const [name, setName] = useState(tpl?.name ?? '')
  const [description, setDescription] = useState(tpl?.description ?? '')
  const [scope, setScope] = useState<'department' | 'position'>(tpl?.scope ?? (prePos ? 'position' : 'department'))
  const [deptId, setDeptId] = useState(String(tpl?.department_id ?? preDept ?? ''))
  const [posId, setPosId] = useState(String(tpl?.position_id ?? prePos ?? ''))
  const [freq, setFreq] = useState<'daily' | 'weekly'>(tpl?.frequency ?? 'daily')
  const [deadline, setDeadline] = useState(tpl?.deadline_time ?? '20:00')
  const [active, setActive] = useState(tpl?.is_active ?? true)
  const [items, setItems] = useState<DutyItem[]>(tpl?.items?.length ? tpl.items : [{ text: '', kind: 'yesno', required: true }])
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const manage = can('duty.manage')
  const patch = (i: number, p: Partial<DutyItem>) => setItems(items.map((x, j) => (j === i ? { ...x, ...p } : x)))
  const move = (i: number, d: number) => {
    const j = i + d
    if (j < 0 || j >= items.length) return
    const next = [...items]
    ;[next[i], next[j]] = [next[j], next[i]]
    setItems(next)
  }
  const save = useMutation({
    mutationFn: () => {
      const body = { name, description: description || null, scope, department_id: scope === 'department' ? Number(deptId) : null, position_id: scope === 'position' ? Number(posId) : null, frequency: freq, deadline_time: deadline, is_active: active, items }
      return tpl ? send('PUT', `/api/v1/duty/templates/${tpl.id}`, body) : send('POST', '/api/v1/duty/templates', body)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['duty'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(LIST)
    },
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/duty/templates/${tpl?.id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['duty'] })
      navigate(LIST)
    },
    onError: (e) => setDeleteError(errorText(t, e)),
  })
  const target = scope === 'department' ? deptId : posId
  const valid = name.trim() && target && items.length > 0 && items.every((x) => x.text.trim())
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <PageHeader title={tpl ? t('duty.edit') : t('duty.add')} subtitle={tpl?.name} backTo={LIST} backLabel={t('duty.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('duty.main')}>
          <Field label={t('duty.name')}>{(fid) => <Input id={fid} value={name} onChange={(e) => setName(e.target.value)} required maxLength={160} autoFocus disabled={!manage} />}</Field>
          <Field label={t('duty.description')}>{(fid) => <Input id={fid} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={300} disabled={!manage} />}</Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('duty.scopeLabel')}>
              {(fid) => (
                <Select id={fid} value={scope} onChange={(e) => setScope(e.target.value as typeof scope)} disabled={!manage}>
                  <option value="department">{t('duty.scope.department')}</option>
                  <option value="position">{t('duty.scope.position')}</option>
                </Select>
              )}
            </Field>
            {scope === 'department' ? (
              <Field label={t('duty.scope.department')}>
                {(fid) => (
                  <Select id={fid} value={deptId} onChange={(e) => setDeptId(e.target.value)} disabled={!manage}>
                    <option value="">—</option>
                    {departments.data?.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            ) : (
              <Field label={t('duty.scope.position')}>
                {(fid) => (
                  <Select id={fid} value={posId} onChange={(e) => setPosId(e.target.value)} disabled={!manage}>
                    <option value="">—</option>
                    {positions.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.label}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            )}
            <Field label={t('duty.frequency')}>
              {(fid) => (
                <Select id={fid} value={freq} onChange={(e) => setFreq(e.target.value as typeof freq)} disabled={!manage}>
                  <option value="daily">{t('duty.freq.daily')}</option>
                  <option value="weekly">{t('duty.freq.weekly')}</option>
                </Select>
              )}
            </Field>
            <Field label={t('duty.deadline')}>{(fid) => <Input id={fid} type="time" value={deadline} onChange={(e) => setDeadline(e.target.value)} disabled={!manage} />}</Field>
          </div>
          <p className="text-xs text-muted">{t(scope === 'department' ? 'duty.scopeHintDept' : 'duty.scopeHintPos')}</p>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4" checked={active} onChange={(e) => setActive(e.target.checked)} disabled={!manage} />
            {t('duty.activeLabel')}
          </label>
        </FormSection>
        <FormSection title={t('duty.items')} description={t('duty.itemsHint')}>
          <ol className="flex flex-col gap-3">
            {items.map((it, i) => (
              <li key={it.id ?? `n${i}`}>
                <Card tint="sand" className="flex flex-col gap-3 p-4">
                  <div className="flex items-center gap-2">
                    <span className="grid size-7 shrink-0 place-items-center rounded-full bg-surface text-xs font-semibold">{i + 1}</span>
                    <Input value={it.text} onChange={(e) => patch(i, { text: e.target.value })} maxLength={300} placeholder={t('duty.itemText')} aria-label={t('duty.itemText')} disabled={!manage} />
                    {manage && (
                      <>
                        <Button variant="ghost" className="h-9 px-2" onClick={() => move(i, -1)} disabled={i === 0} aria-label={t('checklists.templates.up')}>
                          <ArrowUp className="size-4" />
                        </Button>
                        <Button variant="ghost" className="h-9 px-2" onClick={() => move(i, 1)} disabled={i === items.length - 1} aria-label={t('checklists.templates.down')}>
                          <ArrowDown className="size-4" />
                        </Button>
                        <Button variant="ghost" className="h-9 px-2 text-danger" onClick={() => setItems(items.filter((_, j) => j !== i))} disabled={items.length === 1} aria-label={t('common.delete')}>
                          <Trash2 className="size-4" />
                        </Button>
                      </>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-5 text-sm">
                    <Select className="w-auto" value={it.kind} onChange={(e) => patch(i, { kind: e.target.value as DutyItem['kind'] })} aria-label={t('checklists.templates.kind')} disabled={!manage}>
                      <option value="yesno">{t('checklists.templates.yesno')}</option>
                      <option value="score">{t('checklists.templates.score')}</option>
                    </Select>
                    <label className="flex items-center gap-2">
                      <input type="checkbox" className="size-4" checked={it.required} onChange={(e) => patch(i, { required: e.target.checked })} disabled={!manage} />
                      {t('checklists.templates.required')}
                    </label>
                  </div>
                </Card>
              </li>
            ))}
          </ol>
          {manage && (
            <div>
              <Button variant="outline" onClick={() => setItems([...items, { text: '', kind: 'yesno', required: true }])} disabled={items.length >= 60}>
                <Plus className="size-4" />
                {t('checklists.templates.addItem')}
              </Button>
            </div>
          )}
        </FormSection>
        {manage && (
          <FormFooter error={save.isError ? errorText(t, save.error) : null}>
            <Button variant="outline" onClick={() => navigate(LIST)}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" disabled={save.isPending || !valid}>
              {t('common.save')}
            </Button>
          </FormFooter>
        )}
      </form>
      {tpl && manage && (
        <FormSection title={t('org.dangerZone')} description={t('duty.deleteHint')} danger>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              className="text-danger"
              disabled={remove.isPending}
              onClick={async () => {
                if (await confirm({ title: t('duty.delete'), body: t('org.deleteConfirm', { name: tpl.name }), danger: true, confirmLabel: t('common.delete') })) {
                  setDeleteError(null)
                  remove.mutate()
                }
              }}
            >
              <Trash2 className="size-4" />
              {t('duty.delete')}
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

/** /checklists/my: xodimning kunlik/haftalik chek-listi. */
export function MyDutyPage() {
  const { t } = useTranslation()
  const q = useQuery({ queryKey: ['duty', 'my'], queryFn: () => api<MyDuty>('/api/v1/duty/my'), refetchInterval: 120_000 })
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <PageHeader title={t('duty.my.title')} subtitle={q.data?.employee ? t('duty.my.subtitle') : undefined} />
      {!q.data ? (
        <Skeleton className="h-48" />
      ) : q.data.items.length === 0 ? (
        <Card className="p-8 text-center text-muted">{t(q.data.employee ? 'duty.my.none' : 'duty.my.noEmployee')}</Card>
      ) : (
        q.data.items.map((it) => <DutyCard key={it.checklist.id} it={it} />)
      )}
    </div>
  )
}

function DutyCard({ it }: { it: MyDuty['items'][number] }) {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const c = it.checklist
  const [editing, setEditing] = useState(!it.run)
  const [answers, setAnswers] = useState<Record<string, boolean | number>>(it.run?.answers ?? {})
  const [note, setNote] = useState(it.run?.note ?? '')
  const save = useMutation({
    mutationFn: () => send('PUT', `/api/v1/duty/my/${c.id}`, { answers, note: note || null }),
    onSuccess: () => {
      setEditing(false)
      void qc.invalidateQueries({ queryKey: ['duty'] })
      toast.push({ title: t('duty.my.saved'), tone: 'success' })
    },
  })
  const missing = c.items.some((x) => x.required && answers[x.id] === undefined)
  const status: DutyStatus = it.status
  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="font-semibold">{c.name}</h2>
          <p className="text-xs text-muted">
            {t(`duty.freq.${c.frequency}`)} · {t('duty.my.due', { when: formatDateTime(it.due_at, i18n.language) })}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {it.run && <Badge tone={it.run.score_pct >= 80 ? 'success' : 'warning'}>{it.run.score_pct}%</Badge>}
          <Badge tone={STATUS_TONE[status]}>{t(`duty.status.${status}`)}</Badge>
        </div>
      </div>
      <ul className="flex flex-col gap-3">
        {c.items.map((x, i) => (
          <li key={x.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border p-3">
            <span className="text-sm">
              {i + 1}. {x.text}
              {x.required && <span className="text-danger"> *</span>}
            </span>
            {x.kind === 'yesno' ? (
              <div className="flex gap-2">
                {[true, false].map((v) => (
                  <button key={String(v)} type="button" disabled={!editing} aria-pressed={answers[x.id] === v} onClick={() => setAnswers({ ...answers, [x.id]: v })} className={'h-9 rounded-full border px-4 text-sm font-medium ' + (answers[x.id] === v ? (v ? 'border-success bg-success/15 text-success' : 'border-danger bg-danger/10 text-danger') : 'border-border text-muted')}>
                    {t(v ? 'common.yes' : 'common.no')}
                  </button>
                ))}
              </div>
            ) : (
              <div className="flex gap-1.5">
                {[1, 2, 3, 4, 5].map((v) => (
                  <button key={v} type="button" disabled={!editing} aria-pressed={answers[x.id] === v} onClick={() => setAnswers({ ...answers, [x.id]: v })} className={'size-9 rounded-full border text-sm font-medium ' + (answers[x.id] === v ? 'border-primary bg-primary text-primary-fg' : 'border-border text-muted')}>
                    {v}
                  </button>
                ))}
              </div>
            )}
          </li>
        ))}
      </ul>
      {editing ? (
        <>
          <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={1000} placeholder={t('duty.my.note')} aria-label={t('duty.my.note')} className={area} />
          {save.isError && (
            <p role="alert" className="text-sm text-danger">
              {errorText(t, save.error)}
            </p>
          )}
          <div>
            <Button disabled={save.isPending || missing} onClick={() => save.mutate()}>
              <Check className="size-4" />
              {t('duty.my.submit')}
            </Button>
          </div>
        </>
      ) : (
        <div className="flex flex-wrap items-center gap-3 text-sm text-muted">
          {it.run && (
            <span>
              {t('duty.my.doneAt', { when: formatDateTime(it.run.completed_at, i18n.language) })}
              {it.run.late ? ` · ${t('duty.late')}` : ''}
            </span>
          )}
          <Button variant="outline" onClick={() => setEditing(true)}>
            {t('common.edit')}
          </Button>
        </div>
      )}
    </Card>
  )
}

/** /checklists/control: kim chek-listni bajargan, kim bajarmagan. */
export function DutyControlPage() {
  const { t, i18n } = useTranslation()
  const [day, setDay] = useState(todayLocal())
  const [status, setStatus] = useState<'all' | DutyStatus>('all')
  const q = useQuery({ queryKey: ['duty', 'control', day, status], queryFn: () => api<DutyControl>(`/api/v1/duty/control?date=${day}&status=${status}`), placeholderData: (p) => p, refetchInterval: 120_000 })
  const d = q.data
  const kpi = (key: 'all' | DutyStatus, value: number | undefined, label: string) => (
    <button key={key} aria-pressed={status === key} onClick={() => setStatus(key)} className={'rounded-2xl border p-4 text-left transition-colors ' + (status === key ? 'border-primary bg-primary/5' : 'border-border bg-surface hover:bg-surface-2')}>
      <div className="text-2xl font-semibold tabular-nums">{value ?? '—'}</div>
      <div className="text-xs text-muted">{label}</div>
    </button>
  )
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader title={t('duty.control.title')} subtitle={t('duty.control.subtitle')} />
      <Card className="flex flex-wrap items-center gap-3 p-4">
        <label className="text-sm font-medium" htmlFor="duty-day">
          {t('duty.control.date')}
        </label>
        <Input id="duty-day" type="date" className="w-auto" value={day} onChange={(e) => e.target.value && setDay(e.target.value)} />
        {d?.kpis.rate !== null && d?.kpis.rate !== undefined && <span className="ml-auto text-sm text-muted">{t('duty.control.rate', { n: d.kpis.rate })}</span>}
      </Card>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {kpi('all', d?.kpis.expected, t('duty.control.expected'))}
        {kpi('done', d?.kpis.done, t('duty.status.done'))}
        {kpi('open', d?.kpis.open, t('duty.status.open'))}
        {kpi('overdue', d?.kpis.overdue, t('duty.status.overdue'))}
      </div>
      {d && d.by_department.length > 0 && (
        <Card className="flex flex-col gap-2 p-5">
          <h2 className="font-semibold">{t('duty.control.byDept')}</h2>
          {d.by_department.map((x) => (
            <div key={x.name} className="flex items-center gap-3 text-sm">
              <span className="w-44 truncate">{x.name}</span>
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-2">
                <div className="h-full rounded-full bg-primary" style={{ width: `${x.rate}%` }} />
              </div>
              <span className="w-24 text-right tabular-nums text-muted">
                {x.done}/{x.expected} · {x.rate}%
              </span>
            </div>
          ))}
        </Card>
      )}
      {!d ? (
        <Skeleton className="h-48" />
      ) : (
        <div className="flex flex-col gap-2">
          {d.rows.map((r, i) => (
            <Card key={`${r.employee.id}-${r.checklist.id}-${i}`} className="flex flex-wrap items-center justify-between gap-3 p-4">
              <div>
                <div className="font-medium">{r.employee.name}</div>
                <div className="text-sm text-muted">{[r.branch, r.checklist.name, t(`duty.freq.${r.checklist.frequency}`)].filter(Boolean).join(' · ')}</div>
              </div>
              <div className="flex items-center gap-2 text-sm">
                {r.completed_at && <span className="text-muted">{formatDateTime(r.completed_at, i18n.language)}</span>}
                {r.late && <Badge tone="warning">{t('duty.late')}</Badge>}
                {r.score_pct !== null && <Badge>{r.score_pct}%</Badge>}
                <Badge tone={STATUS_TONE[r.status]}>{t(`duty.status.${r.status}`)}</Badge>
              </div>
            </Card>
          ))}
          {d.rows.length === 0 && <Card className="p-8 text-center text-muted">{t('common.empty')}</Card>}
        </div>
      )}
    </div>
  )
}
