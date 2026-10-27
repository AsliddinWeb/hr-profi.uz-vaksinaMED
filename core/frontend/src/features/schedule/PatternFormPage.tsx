import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText, fieldErrors } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import { CycleStrip } from './CycleStrip'
import type { Pattern, Shift } from './api'

const LIST = '/schedule/patterns'

/** /schedule/patterns/new va /schedule/patterns/:id/edit */
export function PatternFormPage() {
  const { id } = useParams()
  const patternId = id ? Number(id) : null
  const pattern = useQuery({
    queryKey: ['schedule', 'patterns', patternId],
    queryFn: () => api<Pattern>(`/api/v1/schedule/patterns/${patternId}`),
    enabled: patternId !== null,
    retry: false,
  })
  if (patternId === null) return <PatternForm pattern={null} />
  if (pattern.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (pattern.error instanceof ApiError && pattern.error.status === 404) return <NotFound />
  if (!pattern.data) return null
  return <PatternForm key={pattern.data.id} pattern={pattern.data} />
}

function PatternForm({ pattern: p }: { pattern: Pattern | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const manage = useCan()('schedule.manage')

  const [name, setName] = useState(p?.name ?? '')
  const [description, setDescription] = useState(p?.description ?? '')
  const [cycle, setCycle] = useState<(number | null)[]>(p?.cycle.map((c) => c.shift_id) ?? [null, null])
  const [active, setActive] = useState(p?.is_active ?? true)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [presetShift, setPresetShift] = useState('')

  const shifts = useQuery({ queryKey: ['schedule', 'shifts'], queryFn: () => api<Shift[]>('/api/v1/schedule/shifts') })
  const usable = (shifts.data ?? []).filter((s) => s.is_active || cycle.includes(s.id))
  const byId = new Map((shifts.data ?? []).map((s) => [s.id, s]))
  const workShift = Number(presetShift) || usable[0]?.id || null

  const preset = (work: number, off: number) => {
    if (workShift === null) return
    setCycle([...Array<number>(work).fill(workShift), ...Array<null>(off).fill(null)])
  }

  const save = useMutation({
    mutationFn: () => {
      const body = { name, description: description || null, cycle: cycle.map((shift_id) => ({ shift_id })), is_active: active }
      return p ? send('PUT', `/api/v1/schedule/patterns/${p.id}`, body) : send('POST', '/api/v1/schedule/patterns', body)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['schedule'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(LIST)
    },
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/schedule/patterns/${p?.id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['schedule'] })
      toast.push({ title: t('schedule.patterns.deleted'), tone: 'success' })
      navigate(LIST)
    },
    onError: (e) => setDeleteError(errorText(t, e)),
  })

  const fe = save.isError ? fieldErrors(t, save.error) : {}
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  const setSlot = (i: number, v: string) => setCycle((c) => c.map((x, j) => (j === i ? (v ? Number(v) : null) : x)))
  const hasWork = cycle.some((c) => c !== null)

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={p ? t('schedule.patterns.edit') : t('schedule.patterns.add')} subtitle={p?.name} backTo={LIST} backLabel={t('schedule.patterns.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('schedule.patterns.sectionMain')}>
          <Field label={t('schedule.patterns.name')} error={fe.name}>
            {(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} required maxLength={80} autoFocus disabled={!manage} placeholder="2/2" />}
          </Field>
          <Field label={t('schedule.groups.description')}>
            {(id) => <Input id={id} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={300} disabled={!manage} />}
          </Field>
        </FormSection>

        <FormSection title={t('schedule.patterns.sectionCycle')} description={t('schedule.patterns.cycleHint')}>
          {manage && (
            <div className="flex flex-wrap items-end gap-3 rounded-control bg-surface-2 p-3">
              <Field label={t('schedule.patterns.presetShift')}>
                {(id) => (
                  <Select id={id} value={presetShift || (workShift?.toString() ?? '')} onChange={(e) => setPresetShift(e.target.value)} className="min-w-48">
                    {usable.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              {([[2, 2], [5, 2], [1, 3], [3, 1]] as const).map(([w, o]) => (
                <Button key={`${w}/${o}`} variant="outline" onClick={() => preset(w, o)} disabled={workShift === null}>
                  {w}/{o}
                </Button>
              ))}
            </div>
          )}
          <ol className="flex flex-col gap-2">
            {cycle.map((slot, i) => (
              <li key={i} className="flex items-center gap-2">
                <span className="w-16 shrink-0 text-sm text-muted tabular-nums">{t('schedule.patterns.dayN', { n: i + 1 })}</span>
                <Select value={slot?.toString() ?? ''} onChange={(e) => setSlot(i, e.target.value)} disabled={!manage} aria-label={t('schedule.patterns.dayN', { n: i + 1 })}>
                  <option value="">{t('schedule.dayOff')}</option>
                  {usable.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} · {s.start_time}–{s.end_time}
                    </option>
                  ))}
                </Select>
                {manage && (
                  <Button variant="ghost" className="h-10 px-2" disabled={cycle.length <= 1} onClick={() => setCycle((c) => c.filter((_, j) => j !== i))} aria-label={t('common.delete')}>
                    <X className="size-4" />
                  </Button>
                )}
              </li>
            ))}
          </ol>
          {manage && (
            <Button variant="outline" className="w-fit" disabled={cycle.length >= 60} onClick={() => setCycle((c) => [...c, null])}>
              <Plus className="size-4" />
              {t('schedule.patterns.addDay')}
            </Button>
          )}
          <div>
            <div className="mb-2 text-sm font-medium">{t('schedule.patterns.preview')}</div>
            <CycleStrip cycle={cycle.map((shift_id) => ({ shift_id }))} shifts={byId} />
          </div>
          {!hasWork && <p className="text-sm text-warning">{t('errors.pattern_no_work_days')}</p>}
        </FormSection>

        {p && (
          <FormSection title={t('schedule.groups.sectionStatus')}>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="size-4" checked={active} onChange={(e) => setActive(e.target.checked)} disabled={!manage} />
              {t('schedule.activeLabel')}
            </label>
          </FormSection>
        )}

        {manage && (
          <FormFooter error={save.isError ? errorText(t, save.error) : null}>
            <Button variant="outline" onClick={() => navigate(LIST)}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" disabled={save.isPending || !name.trim() || !hasWork}>
              {t('common.save')}
            </Button>
          </FormFooter>
        )}
      </form>

      {p && manage && (
        <FormSection title={t('org.dangerZone')} description={t('schedule.patterns.deleteHint')} danger>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              className="text-danger"
              disabled={remove.isPending}
              onClick={async () => {
                if (await confirm({ title: t('schedule.patterns.delete'), body: t('org.deleteConfirm', { name: p.name }), danger: true, confirmLabel: t('common.delete') })) {
                  setDeleteError(null)
                  remove.mutate()
                }
              }}
            >
              <Trash2 className="size-4" />
              {t('schedule.patterns.delete')}
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
