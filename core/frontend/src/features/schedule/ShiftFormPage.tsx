import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Trash2 } from 'lucide-react'
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
import { fmtDuration, SHIFT_COLORS, type Shift } from './api'

const LIST = '/schedule/shifts'

const toMin = (v: string) => {
  const [h, m] = v.split(':').map(Number)
  return (h ?? 0) * 60 + (m ?? 0)
}

/** /schedule/shifts/new va /schedule/shifts/:id/edit */
export function ShiftFormPage() {
  const { id } = useParams()
  const shiftId = id ? Number(id) : null
  const shift = useQuery({
    queryKey: ['schedule', 'shifts', shiftId],
    queryFn: () => api<Shift>(`/api/v1/schedule/shifts/${shiftId}`),
    enabled: shiftId !== null,
    retry: false,
  })
  if (shiftId === null) return <ShiftForm shift={null} />
  if (shift.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (shift.error instanceof ApiError && shift.error.status === 404) return <NotFound />
  if (!shift.data) return null
  return <ShiftForm key={shift.data.id} shift={shift.data} />
}

function ShiftForm({ shift: s }: { shift: Shift | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const manage = useCan()('schedule.manage')

  const [name, setName] = useState(s?.name ?? '')
  const [code, setCode] = useState(s?.code ?? '')
  const [kind, setKind] = useState<'fixed' | 'flexible'>(s?.kind ?? 'fixed')
  const [start, setStart] = useState(s?.start_time ?? '09:00')
  const [end, setEnd] = useState(s?.end_time ?? '18:00')
  const [brk, setBrk] = useState(String(s?.break_minutes ?? 60))
  const [lateGrace, setLateGrace] = useState(String(s?.late_grace_minutes ?? 10))
  const [earlyGrace, setEarlyGrace] = useState(String(s?.early_leave_grace_minutes ?? 0))
  const [minWork, setMinWork] = useState(s?.min_work_minutes ? String(s.min_work_minutes) : '')
  const [track, setTrack] = useState(s?.track_lateness ?? true)
  const [color, setColor] = useState<string | null>(s?.color ?? null)
  const [sort, setSort] = useState(String(s?.sort_order ?? 0))
  const [active, setActive] = useState(s?.is_active ?? true)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const startM = toMin(start)
  const endM = toMin(end)
  const duration = endM > startM ? endM - startM : 1440 - startM + endM
  const overnight = endM <= startM
  const net = duration - (Number(brk) || 0)

  const save = useMutation({
    mutationFn: () => {
      const body = {
        name,
        code: code || null,
        kind,
        start_time: start,
        end_time: end,
        break_minutes: Number(brk) || 0,
        late_grace_minutes: Number(lateGrace) || 0,
        early_leave_grace_minutes: Number(earlyGrace) || 0,
        min_work_minutes: minWork ? Number(minWork) : null,
        track_lateness: track,
        color,
        sort_order: Number(sort) || 0,
        is_active: active,
      }
      return s ? send('PUT', `/api/v1/schedule/shifts/${s.id}`, body) : send('POST', '/api/v1/schedule/shifts', body)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['schedule'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(LIST)
    },
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/schedule/shifts/${s?.id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['schedule'] })
      toast.push({ title: t('schedule.shifts.deleted'), tone: 'success' })
      navigate(LIST)
    },
    onError: (e) => setDeleteError(errorText(t, e)),
  })

  const fe = save.isError ? fieldErrors(t, save.error) : {}
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  const changeKind = (k: 'fixed' | 'flexible') => {
    setKind(k)
    if (!s) setTrack(k === 'fixed')
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={s ? t('schedule.shifts.edit') : t('schedule.shifts.add')} subtitle={s?.name} backTo={LIST} backLabel={t('schedule.shifts.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('schedule.shifts.sectionMain')}>
          <div className="grid gap-4 sm:grid-cols-[1fr_7rem]">
            <Field label={t('schedule.shifts.name')} error={fe.name}>
              {(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} required maxLength={80} autoFocus disabled={!manage} />}
            </Field>
            <Field label={t('schedule.shifts.code')} hint={t('schedule.shifts.codeHint')}>
              {(id) => <Input id={id} value={code} onChange={(e) => setCode(e.target.value)} maxLength={4} disabled={!manage} />}
            </Field>
          </div>
          <Field label={t('schedule.shifts.kind')} hint={t(`schedule.kindHint.${kind}`)}>
            {(id) => (
              <Select id={id} value={kind} onChange={(e) => changeKind(e.target.value as 'fixed' | 'flexible')} disabled={!manage}>
                <option value="fixed">{t('schedule.kind.fixed')}</option>
                <option value="flexible">{t('schedule.kind.flexible')}</option>
              </Select>
            )}
          </Field>
        </FormSection>

        <FormSection title={t('schedule.shifts.sectionTime')} description={t('schedule.shifts.timeHint')}>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={t('schedule.shifts.start')}>
              {(id) => <Input id={id} type="time" value={start} onChange={(e) => setStart(e.target.value)} required disabled={!manage} />}
            </Field>
            <Field label={t('schedule.shifts.end')}>
              {(id) => <Input id={id} type="time" value={end} onChange={(e) => setEnd(e.target.value)} required disabled={!manage} />}
            </Field>
            <Field label={t('schedule.shifts.break')} error={fe.break_minutes}>
              {(id) => <Input id={id} type="number" min={0} max={600} value={brk} onChange={(e) => setBrk(e.target.value)} disabled={!manage} />}
            </Field>
          </div>
          <p className="rounded-control bg-surface-2 px-3 py-2 text-sm">
            {t('schedule.shifts.summary', { total: fmtDuration(duration), net: fmtDuration(Math.max(net, 0)) })}
            {overnight && <span className="ml-2 font-medium text-primary">{start === end ? t('schedule.shifts.h24Hint') : t('schedule.shifts.overnightHint')}</span>}
          </p>
        </FormSection>

        <FormSection title={t('schedule.shifts.sectionRules')} description={t('schedule.shifts.rulesHint')}>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4" checked={track} onChange={(e) => setTrack(e.target.checked)} disabled={!manage} />
            {t('schedule.shifts.trackLateness')}
          </label>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={t('schedule.shifts.lateGrace')}>
              {(id) => <Input id={id} type="number" min={0} max={240} value={lateGrace} onChange={(e) => setLateGrace(e.target.value)} disabled={!manage || !track} />}
            </Field>
            <Field label={t('schedule.shifts.earlyGrace')}>
              {(id) => <Input id={id} type="number" min={0} max={240} value={earlyGrace} onChange={(e) => setEarlyGrace(e.target.value)} disabled={!manage || !track} />}
            </Field>
            <Field label={t('schedule.shifts.minWork')} error={fe.min_work_minutes} hint={t('schedule.shifts.minWorkHint')}>
              {(id) => <Input id={id} type="number" min={1} max={1440} value={minWork} onChange={(e) => setMinWork(e.target.value)} disabled={!manage} />}
            </Field>
          </div>
        </FormSection>

        <FormSection title={t('schedule.shifts.sectionView')}>
          <div className="flex flex-wrap items-center gap-2" role="radiogroup" aria-label={t('schedule.shifts.color')}>
            <button type="button" onClick={() => setColor(null)} disabled={!manage} className={`h-8 rounded-full border px-3 text-xs ${color === null ? 'border-primary text-primary' : 'border-border text-muted'}`}>
              {t('schedule.shifts.colorAuto')}
            </button>
            {SHIFT_COLORS.map((c) => (
              <button
                key={c}
                type="button"
                role="radio"
                aria-checked={color === c}
                aria-label={c}
                disabled={!manage}
                onClick={() => setColor(c)}
                className={`size-8 rounded-full border-2 ${color === c ? 'border-text' : 'border-transparent'}`}
                style={{ background: c }}
              />
            ))}
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('schedule.sort')}>
              {(id) => <Input id={id} type="number" value={sort} onChange={(e) => setSort(e.target.value)} disabled={!manage} />}
            </Field>
          </div>
          {s && (
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="size-4" checked={active} onChange={(e) => setActive(e.target.checked)} disabled={!manage} />
              {t('schedule.activeLabel')}
            </label>
          )}
        </FormSection>

        {manage && (
          <FormFooter error={save.isError ? errorText(t, save.error) : null}>
            <Button variant="outline" onClick={() => navigate(LIST)}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" disabled={save.isPending || !name.trim()}>
              {t('common.save')}
            </Button>
          </FormFooter>
        )}
      </form>

      {s && manage && (
        <FormSection title={t('org.dangerZone')} description={t('schedule.shifts.deleteHint')} danger>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              className="text-danger"
              disabled={remove.isPending}
              onClick={async () => {
                if (await confirm({ title: t('schedule.shifts.delete'), body: t('org.deleteConfirm', { name: s.name }), danger: true, confirmLabel: t('common.delete') })) {
                  setDeleteError(null)
                  remove.mutate()
                }
              }}
            >
              <Trash2 className="size-4" />
              {t('schedule.shifts.delete')}
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
