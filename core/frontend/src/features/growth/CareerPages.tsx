import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, send } from '../../lib/api'
import { errorText } from '../auth/errorText'
import { usePositionOptions } from '../org/usePositionOptions'
import { useCan } from '../auth/useAuth'

interface Level {
  id: number | null
  name: string
  position_id: number | null
  position?: string | null
  salary_min: number | null
  salary_max: number | null
  is_active: boolean
}
interface Promo {
  id: number
  employee: { id: number; name: string | null }
  from: string | null
  to: string | null
  status: 'proposed' | 'applied' | 'rejected'
  source: 'manual' | 'auto'
  basis: string | null
  decision_note: string | null
}
const TONE = { proposed: 'warning', applied: 'success', rejected: 'danger' } as const

/** /career: o'sish takliflari (HRD tasdiqlaydi) va zinapoya/sozlamalarga o'tish. */
export function CareerPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const can = useCan()
  const [note, setNote] = useState<Record<number, string>>({})
  const q = useQuery({ queryKey: ['growth', 'promotions'], queryFn: () => api<{ items: Promo[]; can_decide: boolean }>('/api/v1/growth/promotions') })
  const act = useMutation({
    mutationFn: ({ id, action }: { id: number; action: 'approve' | 'reject' }) => send('POST', `/api/v1/growth/promotions/${id}/decide`, { action, note: note[id] || null }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['growth'] }),
  })
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title={t('growth.career.title')}
        subtitle={t('growth.career.subtitle')}
        actions={
          <div className="flex gap-2">
            {(can('career.propose') || can('career.manage')) && (
              <Link to="/career/new">
                <Button>
                  <Plus className="size-4" />
                  {t('growth.career.propose')}
                </Button>
              </Link>
            )}
            {can('career.manage') && (
              <>
                <Link to="/career/levels">
                  <Button variant="outline">{t('growth.career.ladder')}</Button>
                </Link>
                <Link to="/career/settings">
                  <Button variant="outline">{t('growth.career.settings')}</Button>
                </Link>
              </>
            )}
          </div>
        }
      />
      {!q.data ? (
        <Skeleton className="h-40" />
      ) : (
        <div className="flex flex-col gap-3">
          {q.data.items.map((p) => (
            <Card key={p.id} className="flex flex-col gap-2 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div className="font-medium">{p.employee.name}</div>
                  <div className="text-sm text-muted">{p.from ?? '—'} → {p.to ?? '—'}</div>
                </div>
                <div className="flex gap-2">
                  {p.source === 'auto' && <Badge>{t('growth.career.auto')}</Badge>}
                  <Badge tone={TONE[p.status]}>{t(`growth.career.status.${p.status}`)}</Badge>
                </div>
              </div>
              {p.basis && <p className="text-xs text-muted">{p.basis}</p>}
              {p.decision_note && <p className="text-xs text-muted">{p.decision_note}</p>}
              {p.status === 'proposed' && q.data.can_decide && (
                <div className="flex flex-wrap items-center gap-2">
                  <Input value={note[p.id] ?? ''} onChange={(e) => setNote({ ...note, [p.id]: e.target.value })} maxLength={1000} placeholder={t('answers.decision.note')} aria-label={t('answers.decision.note')} className="max-w-xs" />
                  <Button disabled={act.isPending} onClick={() => act.mutate({ id: p.id, action: 'approve' })}>
                    {t('growth.career.approve')}
                  </Button>
                  <Button variant="outline" className="text-danger" disabled={act.isPending || !(note[p.id] ?? '').trim()} onClick={() => act.mutate({ id: p.id, action: 'reject' })}>
                    {t('growth.career.reject')}
                  </Button>
                </div>
              )}
            </Card>
          ))}
          {q.data.items.length === 0 && <Card className="p-8 text-center text-muted">{t('common.empty')}</Card>}
          {act.isError && <p role="alert" className="text-sm text-danger">{errorText(t, act.error)}</p>}
        </div>
      )}
    </div>
  )
}

/** /career/new: o'sish taklifi. */
export function PromotionFormPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [q, setQ] = useState('')
  const [emp, setEmp] = useState<{ id: number; name: string } | null>(null)
  const [to, setTo] = useState('')
  const [basis, setBasis] = useState('')
  const levels = useQuery({ queryKey: ['growth', 'levels'], queryFn: () => api<Level[]>('/api/v1/growth/levels') })
  const found = useQuery({ queryKey: ['growth', 'emp-search', q], queryFn: () => api<{ items: { id: number; full_name: string }[] }>(`/api/v1/employees?q=${encodeURIComponent(q)}&status=active&size=8`), enabled: q.trim().length >= 2 && !emp })
  const save = useMutation({
    mutationFn: () => send('POST', '/api/v1/growth/promotions', { employee_id: emp?.id, to_level_id: Number(to), basis: basis || null }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['growth'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate('/career', { replace: true })
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={t('growth.career.propose')} backTo="/career" backLabel={t('growth.career.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('growth.career.who')}>
          {emp ? (
            <p className="flex items-center gap-3 text-sm">
              <span className="font-medium">{emp.name}</span>
              <Button variant="outline" className="h-8" onClick={() => setEmp(null)}>
                {t('common.edit')}
              </Button>
            </p>
          ) : (
            <>
              <Field label={t('growth.career.search')}>{(id) => <Input id={id} value={q} onChange={(e) => setQ(e.target.value)} />}</Field>
              <ul className="text-sm">
                {found.data?.items.map((e) => (
                  <li key={e.id}>
                    <button type="button" className="w-full rounded-control px-3 py-2 text-left hover:bg-surface-2" onClick={() => setEmp({ id: e.id, name: e.full_name })}>
                      {e.full_name}
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
          <Field label={t('growth.career.toLevel')}>
            {(id) => (
              <Select id={id} value={to} onChange={(e) => setTo(e.target.value)} required>
                <option value="">—</option>
                {levels.data?.filter((l) => l.is_active).map((l) => (
                  <option key={l.id} value={l.id ?? ''}>
                    {l.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label={t('growth.career.basis')}>{(id) => <textarea id={id} value={basis} onChange={(e) => setBasis(e.target.value)} rows={3} maxLength={1000} className="w-full rounded-control border border-border bg-surface px-3 py-2 text-sm" />}</Field>
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate('/career')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !emp || !to}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}

/** /career/levels: lavozim zinapoyasi (HRD). */
export function LevelsFormPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const q = useQuery({ queryKey: ['growth', 'levels'], queryFn: () => api<Level[]>('/api/v1/growth/levels') })
  const positions = usePositionOptions()
  const [rows, setRows] = useState<Level[] | null>(null)
  const cur = rows ?? q.data
  const save = useMutation({
    mutationFn: () => send('PUT', '/api/v1/growth/levels', { levels: (cur ?? []).map((l) => ({ id: l.id, name: l.name, position_id: l.position_id, salary_min: l.salary_min, salary_max: l.salary_max, is_active: l.is_active })) }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['growth'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate('/career', { replace: true })
    },
  })
  if (!cur) return <Skeleton className="mx-auto h-72 max-w-3xl" />
  const set = (i: number, patch: Partial<Level>) => setRows(cur.map((l, j) => (j === i ? { ...l, ...patch } : l)))
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={t('growth.career.ladder')} subtitle={t('growth.career.ladderHint')} backTo="/career" backLabel={t('growth.career.title')} />
      <FormSection title={t('growth.career.levels')}>
        {cur.map((l, i) => (
          <div key={i} className="grid items-end gap-3 rounded-control border border-border p-3 sm:grid-cols-5">
            <Field label={t('growth.career.levelName')}>{(id) => <Input id={id} value={l.name} onChange={(e) => set(i, { name: e.target.value })} maxLength={120} />}</Field>
            <Field label={t('pharmacy.needs.position')}>
              {(id) => (
                <Select id={id} value={l.position_id ?? ''} onChange={(e) => set(i, { position_id: e.target.value ? Number(e.target.value) : null })}>
                  <option value="">—</option>
                  {positions.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('growth.career.salaryMin')}>{(id) => <Input id={id} type="number" min={0} value={l.salary_min ?? ''} onChange={(e) => set(i, { salary_min: e.target.value ? Number(e.target.value) : null })} />}</Field>
            <Field label={t('growth.career.salaryMax')}>{(id) => <Input id={id} type="number" min={0} value={l.salary_max ?? ''} onChange={(e) => set(i, { salary_max: e.target.value ? Number(e.target.value) : null })} />}</Field>
            <Button variant="outline" className="text-danger" onClick={() => setRows(cur.filter((_, j) => j !== i))} aria-label={t('common.delete')}>
              <Trash2 className="size-4" />
            </Button>
          </div>
        ))}
        <div>
          <Button variant="outline" onClick={() => setRows([...cur, { id: null, name: '', position_id: null, salary_min: null, salary_max: null, is_active: true }])}>
            <Plus className="size-4" />
            {t('growth.career.addLevel')}
          </Button>
        </div>
      </FormSection>
      <FormFooter error={save.isError ? errorText(t, save.error) : null}>
        <Button variant="outline" onClick={() => navigate('/career')}>
          {t('common.cancel')}
        </Button>
        <Button disabled={save.isPending || cur.some((l) => !l.name.trim())} onClick={() => save.mutate()}>
          {t('common.save')}
        </Button>
      </FormFooter>
    </div>
  )
}

const FIELDS = {
  attestation: ['pass_score', 'test_weight', 'practical_weight', 'promote_after'],
  score_weights: ['attendance', 'learning', 'attestation', 'discipline'],
} as const

/** /career/settings: attestatsiya mezoni va yig'ma ball og'irliklari (HRD). */
export function GrowthSettingsPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [vals, setVals] = useState<Record<string, Record<string, string>>>({})
  const att = useQuery({ queryKey: ['growth', 'settings', 'attestation'], queryFn: () => api<Record<string, number>>('/api/v1/growth/settings/attestation') })
  const sw = useQuery({ queryKey: ['growth', 'settings', 'score_weights'], queryFn: () => api<Record<string, number>>('/api/v1/growth/settings/score_weights') })
  const data = { attestation: att.data, score_weights: sw.data }
  const save = useMutation({
    mutationFn: async () => {
      for (const key of ['attestation', 'score_weights'] as const) {
        const merged = { ...(data[key] ?? {}), ...Object.fromEntries(Object.entries(vals[key] ?? {}).map(([k, v]) => [k, Number(v)])) }
        await send('PUT', `/api/v1/growth/settings/${key}`, { value: merged })
      }
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['growth'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate('/career', { replace: true })
    },
  })
  if (!att.data || !sw.data) return <Skeleton className="mx-auto h-72 max-w-3xl" />
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={t('growth.career.settings')} backTo="/career" backLabel={t('growth.career.title')} />
      {(['attestation', 'score_weights'] as const).map((key) => (
        <FormSection key={key} title={t(`growth.settings.${key}`)} description={t(`growth.settings.${key}Hint`)}>
          <div className="grid gap-4 sm:grid-cols-4">
            {FIELDS[key].map((f) => (
              <Field key={f} label={t(`growth.settings.f.${f}`)}>
                {(id) => <Input id={id} type="number" min={0} value={vals[key]?.[f] ?? String(data[key]?.[f] ?? '')} onChange={(e) => setVals({ ...vals, [key]: { ...vals[key], [f]: e.target.value } })} />}
              </Field>
            ))}
          </div>
        </FormSection>
      ))}
      <FormFooter error={save.isError ? errorText(t, save.error) : null}>
        <Button variant="outline" onClick={() => navigate('/career')}>
          {t('common.cancel')}
        </Button>
        <Button disabled={save.isPending} onClick={() => save.mutate()}>
          {t('common.save')}
        </Button>
      </FormFooter>
    </div>
  )
}
