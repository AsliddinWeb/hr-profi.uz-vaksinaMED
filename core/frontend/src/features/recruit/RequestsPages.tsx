import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, ClipboardList, Plus, X } from 'lucide-react'
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
import { Stepper } from '../../components/ui/Stepper'
import { useToast } from '../../components/ui/toastContext'
import { api, send } from '../../lib/api'
import { useCan } from '../auth/useAuth'
import { formatDate, formatDateTime } from '../../lib/format'
import { errorText } from '../auth/errorText'
import { ApprovedProfileCard, type Profile } from './CompetencyPages'

type RStatus = 'pending' | 'approved' | 'rejected' | 'cancelled'
export interface HireRequest {
  id: number
  number: string
  department: { id: number; name: string } | null
  branch: { id: number; name: string } | null
  position: { id: number; name: string } | null
  count: number
  urgency: 'low' | 'normal' | 'urgent'
  needed_from: string | null
  reason: string | null
  requirements: string | null
  salary_from: number | null
  salary_to: number | null
  status: RStatus
  created_at: string
  created_by: string | null
  decided_by: string | null
  decided_at: string | null
  decision_note: string | null
  vacancy_id: number | null
  can: { decide: boolean; cancel: boolean }
}
interface Meta {
  departments: { id: number; name: string }[]
  branches: { id: number; name: string }[]
  positions: { id: number; name: string; department_id: number | null; profile?: { status: string; version: number | null; id: number | null } }[]
  can_request: boolean
  can_decide: boolean
  scope?: 'all' | 'own'
  can_create_position?: boolean
}

const TONE: Record<RStatus, 'warning' | 'success' | 'danger' | 'neutral'> = { pending: 'warning', approved: 'success', rejected: 'danger', cancelled: 'neutral' }
const area = 'w-full rounded-control bg-surface px-3 py-2 text-[13px] shadow-[inset_0_0_0_1px_var(--border-strong)] outline-none focus:ring-2 focus:ring-primary/30'

/** /recruit/requests: bo'lim/filial zayafkalari (lavozim bo'yicha xodim talabi). */
export function RequestsPage() {
  const { t, i18n } = useTranslation()
  const [status, setStatus] = useState<'' | RStatus>('')
  const can = useCan()
  const seeNeeds = can('pharmacy.read') || can('pharmacy.manage') || can('pharmacy.own')
  const meta = useQuery({ queryKey: ['recruit', 'requests', 'meta'], queryFn: () => api<Meta>('/api/v1/recruit/requests/meta') })
  const q = useQuery({ queryKey: ['recruit', 'requests', status], queryFn: () => api<{ items: HireRequest[] }>(`/api/v1/recruit/requests${status ? `?status=${status}` : ''}`) })
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <PageHeader
        title={t('rreq.title')}
        subtitle={t('rreq.subtitle')}
        actions={
          meta.data?.can_request && (
            <Link to="/recruit/requests/new">
              <Button>
                <Plus className="size-4" />
                {t('rreq.new')}
              </Button>
            </Link>
          )
        }
      />
      {seeNeeds && (
        <Card className="flex flex-wrap items-center gap-3 border-l-4 border-l-primary p-4 text-sm">
          <span className="flex-1 text-muted">{t('rreq.needsHint')}</span>
          <Link to="/pharmacy/needs" className="font-semibold text-primary hover:underline">
            {t('rreq.needsLink')}
          </Link>
        </Card>
      )}
      <div className="flex flex-wrap gap-2">
        {(['', 'pending', 'approved', 'rejected', 'cancelled'] as const).map((s) => (
          <button key={s} type="button" onClick={() => setStatus(s)} className={`rounded-full px-3 py-1.5 text-xs font-semibold ${status === s ? 'bg-primary text-primary-fg' : 'border border-border bg-surface hover:bg-surface-2'}`}>
            {s ? t(`rreq.status.${s}`) : t('rreq.all')}
          </button>
        ))}
      </div>
      {!q.data ? (
        <Skeleton className="h-48" />
      ) : q.data.items.length === 0 ? (
        <Card className="flex flex-col items-center gap-2 p-10 text-center text-sm text-muted">
          <ClipboardList className="size-8" />
          {t('rreq.empty')}
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border text-xs text-muted">
                <tr>
                  <th className="px-4 py-2.5 font-medium">№</th>
                  <th className="px-4 py-2.5 font-medium">{t('rreq.position')}</th>
                  <th className="px-4 py-2.5 font-medium">{t('rreq.unit')}</th>
                  <th className="px-4 py-2.5 font-medium">{t('rreq.count')}</th>
                  <th className="hidden px-4 py-2.5 font-medium md:table-cell">{t('rreq.created')}</th>
                  <th className="px-4 py-2.5 font-medium">{t('rreq.statusLabel')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {q.data.items.map((r) => (
                  <tr key={r.id}>
                    <td className="px-4 py-2.5">
                      <Link to={`/recruit/requests/${r.id}`} className="font-medium text-primary hover:underline">
                        {r.number}
                      </Link>
                    </td>
                    <td className="px-4 py-2.5 font-medium">{r.position?.name ?? '—'}</td>
                    <td className="px-4 py-2.5 text-muted">{r.department?.name ?? r.branch?.name ?? '—'}</td>
                    <td className="px-4 py-2.5 tabular-nums">
                      {r.count}
                      {r.urgency === 'urgent' && (
                        <Badge tone="danger" className="ml-1.5">
                          {t('rreq.urgent')}
                        </Badge>
                      )}
                    </td>
                    <td className="hidden px-4 py-2.5 text-muted md:table-cell">
                      {formatDate(r.created_at, i18n.language)} · {r.created_by ?? '—'}
                    </td>
                    <td className="px-4 py-2.5">
                      <Badge tone={TONE[r.status]}>{t(`rreq.status.${r.status}`)}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}

/** /recruit/requests/new: yangi zayafka (alohida sahifa). Talablar lavozim kompetensiya kartochkasidan avto-to'ldiriladi. */
export function RequestFormPage() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const toast = useToast()
  const qc = useQueryClient()
  const meta = useQuery({ queryKey: ['recruit', 'requests', 'meta'], queryFn: () => api<Meta>('/api/v1/recruit/requests/meta') })
  const [unit, setUnit] = useState('')
  const [pos, setPos] = useState('')
  const [count, setCount] = useState(1)
  const [urgency, setUrgency] = useState('normal')
  const [from, setFrom] = useState('')
  const [reason, setReason] = useState('')
  const [reqs, setReqs] = useState('')
  const [sFrom, setSFrom] = useState('')
  const [sTo, setSTo] = useState('')
  const [noProfile, setNoProfile] = useState(false)
  const [step, setStep] = useState(0)
  const [filledFrom, setFilledFrom] = useState<number | null>(null)
  const prof = useQuery({ queryKey: ['profiles', 'approved', pos], queryFn: () => api<{ profile: Profile | null; required: boolean }>(`/api/v1/recruit/profiles/approved/${pos}`), enabled: !!pos })
  const loadCard = async (positionId: string) => {
    setPos(positionId)
    if (!positionId) return
    const r = await api<{ requirements: string | null; card: boolean }>(`/api/v1/recruit/requests/requirements/${positionId}`).catch(() => null)
    if (r?.requirements && !reqs.trim()) setReqs(r.requirements)
  }
  const save = useMutation({
    mutationFn: () => {
      const [kind, id] = unit.split(':')
      return send<HireRequest>('POST', '/api/v1/recruit/requests', {
        department_id: kind === 'd' ? Number(id) : null, branch_id: kind === 'b' ? Number(id) : null, position_id: Number(pos), count, urgency,
        needed_from: from || null, reason: reason || null, requirements: reqs || null, salary_from: sFrom ? Number(sFrom) : null, salary_to: sTo ? Number(sTo) : null,
      }) // prettier-ignore
    },
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['recruit', 'requests'] })
      toast.push({ title: t('rreq.created2', { n: r.number }), tone: 'success' })
      navigate(`/recruit/requests/${r.id}`, { replace: true })
    },
  })
  const m = meta.data
  if (!m) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  const units = [...m.departments.map((d) => ({ key: `d:${d.id}`, name: d.name })), ...m.branches.map((b) => ({ key: `b:${b.id}`, name: b.name }))]
  // bo'lim boshlig'i (o'z doirasi, bitta bo'lim): bo'lim avtomatik
  const onlyUnit = m.scope !== 'all' && units.length === 1 ? units[0] : null
  if (onlyUnit && unit !== onlyUnit.key) setUnit(onlyUnit.key)
  const [ukind, uid] = unit.split(':')
  const unitPositions = !unit ? [] : ukind === 'd' ? m.positions.filter((x) => x.department_id === Number(uid) || x.department_id == null) : m.positions
  const selPos = m.positions.find((x) => String(x.id) === pos)
  const approved = prof.data?.profile
  // tasdiqlangan profildan talablar matni (bir marta, talablar bo'sh bo'lsa)
  if (approved && filledFrom !== approved.id) {
    setFilledFrom(approved.id)
    if (!reqs.trim()) setReqs(profileText(approved, t))
  }
  const checklist: [string, boolean][] = [
    ['unit', !!unit],
    ['position', !!pos],
    ['profile', !!approved],
    ['details', count > 0 && !!reason.trim()],
  ]
  return (
    <form
      className="mx-auto flex max-w-5xl flex-col gap-5"
      onSubmit={(e: FormEvent) => {
        e.preventDefault()
        if (step === 2) save.mutate()
      }}
    >
      <PageHeader title={t('rreq.new')} backTo="/recruit/requests" backLabel={t('rreq.title')} />
      {!m.can_request && <Card className="p-5 text-sm text-warning">{t('rreq.noRights')}</Card>}
      <Card className="p-5">
        <Stepper steps={['info', 'reqs', 'confirm'].map((k) => ({ key: k, label: t(`rreq.step.${k}`) }))} current={step} label={t('rreq.new')} />
      </Card>
      <div className="grid gap-5 lg:grid-cols-[1fr_300px]">
        <div className="flex flex-col gap-5">
          {step === 0 && (
            <FormSection title={t('rreq.step.info')}>
              <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t('rreq.unit')}>
            {(id) =>
              onlyUnit ? (
                <div id={id} className="flex h-9 items-center gap-2 rounded-control border border-border bg-surface-2 px-3 text-sm">
                  {onlyUnit.name}
                  <Badge tone="info">{t('rreq.auto')}</Badge>
                </div>
              ) : (
                <Select id={id} value={unit} onChange={(e) => (setUnit(e.target.value), setPos(''))} required>
                  <option value="">{t('rreq.pickUnit')}</option>
                  {m.departments.length > 0 && (
                    <optgroup label={t('rreq.departments')}>
                      {m.departments.map((d) => (
                        <option key={`d${d.id}`} value={`d:${d.id}`}>
                          {d.name}
                        </option>
                      ))}
                    </optgroup>
                  )}
                  {m.branches.length > 0 && (
                    <optgroup label={t('rreq.branches')}>
                      {m.branches.map((b) => (
                        <option key={`b${b.id}`} value={`b:${b.id}`}>
                          {b.name}
                        </option>
                      ))}
                    </optgroup>
                  )}
                </Select>
              )
            }
          </Field>
          <Field label={t('rreq.position')}>
            {(id) => (
              <Select id={id} value={pos} disabled={!unit} onChange={(e) => void loadCard(e.target.value)} required>
                <option value="">{unit ? '—' : t('rreq.pickUnitFirst')}</option>
                {unitPositions.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} — {t(`rreq.pst.${p.profile?.status ?? 'none'}`)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          {unit && (
            <div className="rounded-control border border-dashed border-border px-3 py-2 text-xs text-muted sm:col-span-2">
              {t('rreq.noPositionHint')}{' '}
              {m.can_create_position && (
                <Link to="/org/positions" className="text-primary hover:underline">
                  {t('rreq.createPosition')}
                </Link>
              )}
              {m.can_create_position && ' · '}
              <Link to="/recruit/profiles" className="text-primary hover:underline">
                {t('rreq.fillProfile')}
              </Link>
            </div>
          )}
          <Field label={t('rreq.count')}>
            {(id) => (
              <div className="flex items-center gap-1">
                <Button type="button" variant="outline" className="size-9 px-0" aria-label="-" onClick={() => setCount(Math.max(1, count - 1))}>−</Button>
                <Input id={id} type="number" min={1} max={100} value={count} onChange={(e) => setCount(Number(e.target.value))} className="w-20 text-center" />
                <Button type="button" variant="outline" className="size-9 px-0" aria-label="+" onClick={() => setCount(Math.min(100, count + 1))}>+</Button>
              </div>
            )}
          </Field>
          <Field label={t('rreq.urgency')}>
            {(id) => (
              <Select id={id} value={urgency} onChange={(e) => setUrgency(e.target.value)}>
                {['low', 'normal', 'urgent'].map((u) => (
                  <option key={u} value={u}>
                    {t(`rreq.urg.${u}`)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label={t('rreq.neededFrom')}>{(id) => <Input id={id} type="date" value={from} onChange={(e) => setFrom(e.target.value)} />}</Field>
          <div className="grid grid-cols-2 gap-2">
            <Field label={t('rreq.salaryFrom')}>{(id) => <Input id={id} type="number" min={0} value={sFrom} onChange={(e) => setSFrom(e.target.value)} />}</Field>
            <Field label={t('rreq.salaryTo')}>{(id) => <Input id={id} type="number" min={0} value={sTo} onChange={(e) => setSTo(e.target.value)} />}</Field>
          </div>
              </div>
              <Field label={t('rreq.reason')}>{(id) => <textarea id={id} rows={2} maxLength={2000} value={reason} onChange={(e) => setReason(e.target.value)} className={area} />}</Field>
            </FormSection>
          )}
          {step === 1 && (
            <FormSection title={t('rreq.step.reqs')} description={t('rreq.detailsHint')}>
              {approved && <div className="rounded-lg bg-success/10 px-3 py-2 text-sm text-success">{t('rreq.fromProfile', { v: approved.version })}</div>}
              {prof.data?.profile && prof.data.profile.competencies.length > 0 && (
                <div className="flex flex-col gap-1.5">
                  <div className="text-sm font-medium">{t('rreq.profileComps')}</div>
                  <div className="flex flex-wrap gap-1.5">
                    {prof.data.profile.competencies.map((c) => (
                      <Badge key={c.competency_id} tone={c.mandatory ? 'danger' : 'warning'}>
                        {c.name} · L{c.required_level}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
              <Field label={t('rreq.requirements')} hint={t('rreq.requirementsHint')}>
          {(id) => <textarea id={id} rows={8} maxLength={10000} value={reqs} onChange={(e) => setReqs(e.target.value)} className={area} />}
        </Field>
            </FormSection>
          )}
          {step === 2 && (
            <FormSection title={t('rreq.step.confirm')}>
              <dl className="grid gap-2 text-sm sm:grid-cols-2">
                {[
                  [t('rreq.position'), m.positions.find((x) => String(x.id) === pos)?.name],
                  [t('rreq.unit'), [...m.departments.map((d) => [`d:${d.id}`, d.name]), ...m.branches.map((b) => [`b:${b.id}`, b.name])].find(([k]) => k === unit)?.[1]],
                  [t('rreq.count'), String(count)],
                  [t('rreq.urgency'), t(`rreq.urg.${urgency}`)],
                  [t('rreq.neededFrom'), from ? formatDate(from, i18n.language) : null],
                  [t('rreq.salary'), sFrom || sTo ? `${sFrom || '…'} – ${sTo || '…'}` : null],
                  [t('rreq.reason'), reason || null],
                ].map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-3 rounded-lg bg-surface-2 px-3 py-2">
                    <dt className="text-muted">{k}</dt>
                    <dd className="text-right font-medium">{v || '—'}</dd>
                  </div>
                ))}
              </dl>
              {reqs && <p className="whitespace-pre-wrap text-sm text-muted">{reqs}</p>}
            </FormSection>
          )}
          <FormFooter error={save.isError ? errorText(t, save.error) : null}>
            {step === 0 ? (
              <Link to="/recruit/requests">
                <Button variant="outline">{t('common.cancel')}</Button>
              </Link>
            ) : (
              <Button type="button" variant="outline" onClick={() => setStep(step - 1)}>
                {t('rreq.back')}
              </Button>
            )}
            {step < 2 ? (
              <Button type="button" disabled={!unit || !pos || noProfile} onClick={() => setStep(step + 1)}>
                {t('rreq.next')}
              </Button>
            ) : (
              <Button type="submit" disabled={save.isPending || !m.can_request || !unit || !pos || noProfile}>
                {t('rreq.submit')}
              </Button>
            )}
          </FormFooter>
        </div>
        <div className="flex h-fit flex-col gap-3 lg:sticky lg:top-4">
          <Card className="flex flex-col gap-2 p-4 text-sm">
            <div className="font-medium">{t('rreq.check.title')}</div>
            {checklist.map(([k, ok], i) => (
              <div key={k} className="flex items-start gap-2">
                <span className={`mt-0.5 grid size-5 shrink-0 place-items-center rounded-full text-[11px] ${ok ? 'bg-success text-white' : 'bg-surface-2 text-muted'}`}>{ok ? <Check className="size-3" /> : i + 1}</span>
                <span className={ok ? '' : 'text-muted'}>{t(`rreq.check.${k}`)}</span>
              </div>
            ))}
            {selPos && selPos.profile?.status !== 'approved' && (
              <div className="mt-1 rounded-lg bg-warning/10 p-2 text-xs text-warning">{t(`rreq.check.todo_${selPos.profile?.status === 'pending' ? 'pending' : 'fill'}`)}</div>
            )}
          </Card>
          {pos ? <ApprovedProfileCard positionId={pos} onState={setNoProfile} /> : <Card className="p-4 text-sm text-muted">{t('rreq.pickPosition')}</Card>}
          {!noProfile && <Card className="p-4 text-xs text-muted">{t('comp.req.noProfileHint')}</Card>}
        </div>
      </div>
    </form>
  )
}

/** /recruit/requests/:id: zayafka tafsiloti; HR tasdiqlaydi (vakansiya ochiladi) yoki sabab bilan rad etadi. */
export function RequestDetailPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const toast = useToast()
  const qc = useQueryClient()
  const [note, setNote] = useState('')
  const q = useQuery({ queryKey: ['recruit', 'requests', 'one', id], queryFn: () => api<HireRequest>(`/api/v1/recruit/requests/${id}`) })
  const act = useMutation({
    mutationFn: (body: { path: string; data?: unknown }) => send<HireRequest>('POST', `/api/v1/recruit/requests/${id}/${body.path}`, body.data ?? {}),
    onSuccess: (r) => {
      qc.setQueryData(['recruit', 'requests', 'one', id], r)
      void qc.invalidateQueries({ queryKey: ['recruit'] })
      toast.push({ title: t(`rreq.status.${r.status}`), tone: r.status === 'approved' ? 'success' : 'info' })
    },
    onError: (e) => toast.push({ title: errorText(t, e), tone: 'danger' }),
  })
  const r = q.data
  if (!r) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <PageHeader title={`${r.number} · ${r.position?.name ?? ''}`} subtitle={r.department?.name ?? r.branch?.name ?? undefined} backTo="/recruit/requests" backLabel={t('rreq.title')} />
      <Card className="flex flex-col gap-3 p-5">
        <div className="flex flex-wrap gap-2">
          <Badge tone={TONE[r.status]}>{t(`rreq.status.${r.status}`)}</Badge>
          <Badge tone={r.urgency === 'urgent' ? 'danger' : 'neutral'}>{t(`rreq.urg.${r.urgency}`)}</Badge>
          <Badge>{t('rreq.countN', { n: r.count })}</Badge>
        </div>
        <dl className="grid gap-2 text-sm sm:grid-cols-2">
          <Item k={t('rreq.created')} v={`${formatDateTime(r.created_at, i18n.language)} · ${r.created_by ?? '—'}`} />
          <Item k={t('rreq.neededFrom')} v={r.needed_from ? formatDate(r.needed_from, i18n.language) : '—'} />
          <Item k={t('rreq.salary')} v={r.salary_from || r.salary_to ? `${r.salary_from ?? '…'} – ${r.salary_to ?? '…'}` : '—'} />
          {r.decided_at && <Item k={t('rreq.decided')} v={`${formatDateTime(r.decided_at, i18n.language)} · ${r.decided_by ?? '—'}`} />}
        </dl>
        {r.reason && <p className="whitespace-pre-wrap text-sm">{r.reason}</p>}
        {r.requirements && (
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-muted">{t('rreq.requirements')}</div>
            <p className="mt-1 whitespace-pre-wrap text-sm">{r.requirements}</p>
          </div>
        )}
        {r.decision_note && <p className="rounded-control bg-surface-2 p-3 text-sm">{r.decision_note}</p>}
        {r.vacancy_id && (
          <Link to={`/recruit/vacancies/${r.vacancy_id}`} className="self-start">
            <Button>{t('rreq.openVacancy')}</Button>
          </Link>
        )}
      </Card>
      {(r.can.decide || r.can.cancel) && (
        <FormSection title={t('rreq.decision')}>
          {r.can.decide && <Field label={t('rreq.note')}>{(fid) => <textarea id={fid} rows={2} value={note} onChange={(e) => setNote(e.target.value)} className={area} />}</Field>}
          <div className="flex flex-wrap gap-2">
            {r.can.decide && (
              <>
                <Button disabled={act.isPending} onClick={() => act.mutate({ path: 'decide', data: { action: 'approve', note: note || null } })}>
                  <Check className="size-4" />
                  {t('rreq.approve')}
                </Button>
                <Button variant="outline" className="text-danger" disabled={act.isPending || !note.trim()} onClick={() => act.mutate({ path: 'decide', data: { action: 'reject', note } })}>
                  <X className="size-4" />
                  {t('rreq.reject')}
                </Button>
              </>
            )}
            {r.can.cancel && (
              <Button variant="ghost" disabled={act.isPending} onClick={() => act.mutate({ path: 'cancel' })}>
                {t('rreq.cancel')}
              </Button>
            )}
          </div>
        </FormSection>
      )}
    </div>
  )
}

function Item({ k, v }: { k: string; v: string }) {
  return (
    <div>
      <dt className="text-xs text-muted">{k}</dt>
      <dd className="font-medium">{v}</dd>
    </div>
  )
}

/** Tasdiqlangan lavozim profilidan zayavka talablari matni. */
function profileText(p: Profile, t: (k: string, o?: Record<string, unknown>) => string): string {
  const d = p.data as { goal?: string; functions?: string[]; education?: Record<string, string>; kpi?: { name: string; target: string }[]; portrait?: string }
  const lines: string[] = []
  if (d.goal) lines.push(`${t('comp.wiz.step.goal')}: ${d.goal}`)
  if (d.functions?.length) lines.push(`${t('comp.wiz.step.functions')}:`, ...d.functions.filter(Boolean).map((f) => `- ${f}`))
  const edu = Object.values(d.education ?? {}).filter(Boolean)
  if (edu.length) lines.push(`${t('comp.wiz.step.education')}: ${edu.join('; ')}`)
  const comps = p.competencies.filter((c) => c.category !== 'knowledge' && c.category !== 'experience')
  if (comps.length) lines.push(`${t('rreq.profileComps')}:`, ...comps.map((c) => `- ${c.name} (L${c.required_level}${c.mandatory ? '' : ', ' + t('comp.wiz.extra')})`))
  if (d.kpi?.length) lines.push(`${t('comp.wiz.step.kpi')}:`, ...d.kpi.filter((k) => k.name).map((k) => `- ${k.name}${k.target ? ': ' + k.target : ''}`))
  if (d.portrait) lines.push(`${t('comp.wiz.step.portrait')}: ${d.portrait}`)
  return lines.join('\n')
}
