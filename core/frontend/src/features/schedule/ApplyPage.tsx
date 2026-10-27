import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation, useNavigate } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { useToast } from '../../components/ui/toastContext'
import { api, send } from '../../lib/api'
import type { BranchPage } from '../branches/api'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import type { DepartmentRow } from '../org/api'
import { orderTree } from '../org/tree'
import { currentMonth, monthRange, type ApplyResult, type Pattern, type Shift, type WorkGroup } from './api'
import { WeekdayPicker } from './WeekdayPicker'

const MODES = ['shift', 'pattern', 'off', 'clear'] as const
type Mode = (typeof MODES)[number]

/** /schedule/apply: tanlangan xodimlarga sana oralig'ida grafik tuzish (avval ko'rib chiqish, keyin qo'llash). */
export function ApplyPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const can = useCan()
  const state = useLocation().state as { ids?: number[]; names?: string[]; month?: string } | null
  const range = monthRange(state?.month ?? currentMonth())

  const [ids, setIds] = useState<number[]>(state?.ids ?? [])
  const [groupId, setGroupId] = useState('')
  const [departmentId, setDepartmentId] = useState('')
  const [branchId, setBranchId] = useState('')
  const [start, setStart] = useState(range.start)
  const [end, setEnd] = useState(range.end)
  const [weekdays, setWeekdays] = useState<number[]>([0, 1, 2, 3, 4, 5, 6])
  const [mode, setMode] = useState<Mode>('shift')
  const [shiftId, setShiftId] = useState('')
  const [patternId, setPatternId] = useState('')
  const [startIndex, setStartIndex] = useState('0')
  const [stagger, setStagger] = useState(false)
  const [skipHolidays, setSkipHolidays] = useState(true)
  const [overwrite, setOverwrite] = useState(true)
  const [preview, setPreview] = useState<ApplyResult | null>(null)

  const groups = useQuery({ queryKey: ['schedule', 'groups'], queryFn: () => api<WorkGroup[]>('/api/v1/schedule/groups') })
  const shifts = useQuery({ queryKey: ['schedule', 'shifts'], queryFn: () => api<Shift[]>('/api/v1/schedule/shifts') })
  const patterns = useQuery({ queryKey: ['schedule', 'patterns'], queryFn: () => api<Pattern[]>('/api/v1/schedule/patterns') })
  const departments = useQuery({ queryKey: ['org', 'departments'], queryFn: () => api<DepartmentRow[]>('/api/v1/org/departments'), enabled: can('org.read') })
  const branches = useQuery({ queryKey: ['branches', 'select'], queryFn: () => api<BranchPage>('/api/v1/branches?size=200'), enabled: can('branches.read') })
  const tree = orderTree(departments.data ?? [])

  const body = (dry: boolean) => ({
    employee_ids: ids.length ? ids : null,
    group_id: groupId ? Number(groupId) : null,
    department_id: departmentId ? Number(departmentId) : null,
    branch_id: branchId ? Number(branchId) : null,
    start,
    end,
    weekdays,
    mode,
    shift_id: mode === 'shift' ? Number(shiftId) || null : null,
    pattern_id: mode === 'pattern' ? Number(patternId) || null : null,
    start_index: Number(startIndex) || 0,
    stagger,
    skip_holidays: skipHolidays,
    overwrite,
    dry_run: dry,
  })

  const invalidate = () => setPreview(null)
  const run = useMutation({
    mutationFn: (dry: boolean) => send<ApplyResult>('POST', '/api/v1/schedule/apply', body(dry)),
    onSuccess: (res, dry) => {
      if (dry) return setPreview(res)
      void qc.invalidateQueries({ queryKey: ['schedule'] })
      toast.push({ title: t('schedule.apply.done', { count: res.to_create + res.to_update + res.to_delete }), tone: 'success' })
      navigate(`/schedule?month=${start.slice(0, 7)}`)
    },
  })

  const hasTarget = ids.length > 0 || !!groupId || !!departmentId || !!branchId
  const modeOk = (mode === 'shift' && shiftId) || (mode === 'pattern' && patternId) || mode === 'off' || mode === 'clear'
  const valid = hasTarget && !!modeOk && !!start && !!end && end >= start && weekdays.length > 0
  const total = preview ? preview.to_create + preview.to_update + preview.to_delete : 0

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (valid) run.mutate(true)
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={t('schedule.apply.title')} subtitle={t('schedule.apply.subtitle')} backTo="/schedule" backLabel={t('schedule.title')} />

      <form onSubmit={submit} className="flex flex-col gap-6" onChange={invalidate}>
        <FormSection title={t('schedule.apply.who')} description={t('schedule.apply.whoHint')}>
          {ids.length > 0 && (
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">{t('schedule.apply.selectedEmployees', { count: ids.length })}</span>
                <Button variant="ghost" className="h-8 px-2" onClick={() => (setIds([]), invalidate())}>
                  {t('common.clear')}
                </Button>
              </div>
              <div className="flex max-h-28 flex-wrap gap-1.5 overflow-auto">
                {state?.names?.map((n, i) => (
                  <Badge key={state.ids?.[i]}>{n}</Badge>
                ))}
              </div>
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={t('schedule.groups.title')}>
              {(id) => (
                <Select id={id} value={groupId} onChange={(e) => setGroupId(e.target.value)}>
                  <option value="">—</option>
                  {groups.data?.map((g) => (
                    <option key={g.id} value={g.id}>
                      {g.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            {can('org.read') && (
              <Field label={t('employees.department')}>
                {(id) => (
                  <Select id={id} value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>
                    <option value="">—</option>
                    {tree.map((d) => (
                      <option key={d.id} value={d.id}>
                        {'— '.repeat(d.depth - 1)}
                        {d.name}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            )}
            {can('branches.read') && (
              <Field label={t('employees.branch')}>
                {(id) => (
                  <Select id={id} value={branchId} onChange={(e) => setBranchId(e.target.value)}>
                    <option value="">—</option>
                    {branches.data?.items.map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.number ? `№${b.number} · ` : ''}
                        {b.name}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            )}
          </div>
          <p className="text-xs text-muted">{t('schedule.apply.intersectHint')}</p>
        </FormSection>

        <FormSection title={t('schedule.apply.when')}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('schedule.apply.from')}>{(id) => <Input id={id} type="date" value={start} onChange={(e) => setStart(e.target.value)} required />}</Field>
            <Field label={t('schedule.apply.to')} error={end < start ? t('errors.range_invalid') : null}>
              {(id) => <Input id={id} type="date" value={end} min={start} onChange={(e) => setEnd(e.target.value)} required />}
            </Field>
          </div>
          <div className="flex flex-col gap-2">
            <span className="text-sm font-medium">{t('schedule.apply.weekdays')}</span>
            <WeekdayPicker value={weekdays} onChange={(v) => (setWeekdays(v), invalidate())} label={t('schedule.apply.weekdays')} />
          </div>
        </FormSection>

        <FormSection title={t('schedule.apply.what')}>
          <div className="grid gap-2 sm:grid-cols-4" role="radiogroup" aria-label={t('schedule.apply.what')}>
            {MODES.map((m) => (
              <button
                key={m}
                type="button"
                role="radio"
                aria-checked={mode === m}
                onClick={() => (setMode(m), invalidate())}
                className={'rounded-control border px-3 py-2.5 text-left text-sm ' + (mode === m ? 'border-primary bg-primary/10 font-medium' : 'border-border hover:bg-surface-2')}
              >
                {t(`schedule.apply.modes.${m}`)}
                <span className="mt-0.5 block text-xs font-normal text-muted">{t(`schedule.apply.modeHint.${m}`)}</span>
              </button>
            ))}
          </div>

          {mode === 'shift' && (
            <Field label={t('schedule.shifts.title')}>
              {(id) => (
                <Select id={id} value={shiftId} onChange={(e) => setShiftId(e.target.value)}>
                  <option value="">{t('schedule.chooseShift')}</option>
                  {shifts.data
                    ?.filter((s) => s.is_active)
                    .map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name} · {s.start_time}–{s.end_time}
                      </option>
                    ))}
                </Select>
              )}
            </Field>
          )}
          {mode === 'pattern' && (
            <>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label={t('schedule.patterns.title')}>
                  {(id) => (
                    <Select id={id} value={patternId} onChange={(e) => setPatternId(e.target.value)}>
                      <option value="">{t('schedule.apply.choosePattern')}</option>
                      {patterns.data
                        ?.filter((p) => p.is_active)
                        .map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.name} ({p.length})
                          </option>
                        ))}
                    </Select>
                  )}
                </Field>
                <Field label={t('schedule.apply.startIndex')} hint={t('schedule.apply.startIndexHint')}>
                  {(id) => <Input id={id} type="number" min={0} max={59} value={startIndex} onChange={(e) => setStartIndex(e.target.value)} />}
                </Field>
              </div>
              <label className="flex items-start gap-2 text-sm">
                <input type="checkbox" className="mt-0.5 size-4" checked={stagger} onChange={(e) => setStagger(e.target.checked)} />
                <span>
                  {t('schedule.apply.stagger')}
                  <span className="block text-xs text-muted">{t('schedule.apply.staggerHint')}</span>
                </span>
              </label>
            </>
          )}
          {mode !== 'clear' && (
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" className="mt-0.5 size-4" checked={overwrite} onChange={(e) => setOverwrite(e.target.checked)} />
              <span>
                {t('schedule.apply.overwrite')}
                <span className="block text-xs text-muted">{t('schedule.apply.overwriteHint')}</span>
              </span>
            </label>
          )}
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" className="mt-0.5 size-4" checked={skipHolidays} onChange={(e) => setSkipHolidays(e.target.checked)} />
            <span>
              {t('schedule.apply.skipHolidays')}
              <span className="block text-xs text-muted">{t('schedule.apply.skipHolidaysHint')}</span>
            </span>
          </label>
        </FormSection>

        {preview && (
          <Card tint={total ? 'mint' : 'sand'} className="p-5" role="status">
            <h2 className="font-semibold">{t('schedule.apply.preview')}</h2>
            <dl className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-5">
              <Stat label={t('schedule.apply.pEmployees')} value={preview.employees} />
              <Stat label={t('schedule.apply.pCreate')} value={preview.to_create} />
              <Stat label={t('schedule.apply.pUpdate')} value={preview.to_update} />
              <Stat label={t('schedule.apply.pDelete')} value={preview.to_delete} />
              <Stat label={t('schedule.apply.pSkipped')} value={preview.skipped} />
            </dl>
            {total === 0 && <p className="mt-3 text-sm text-muted">{t('schedule.apply.nothing')}</p>}
          </Card>
        )}

        <FormFooter error={run.isError ? errorText(t, run.error) : null}>
          <Button variant="outline" onClick={() => navigate('/schedule')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" variant="outline" disabled={!valid || run.isPending}>
            {t('schedule.apply.previewBtn')}
          </Button>
          <Button disabled={!valid || !preview || total === 0 || run.isPending} onClick={() => run.mutate(false)} className={mode === 'clear' ? 'bg-danger text-white hover:opacity-90' : undefined}>
            {t('schedule.apply.run', { count: total })}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dt className="text-muted">{label}</dt>
      <dd className="mt-0.5 text-2xl font-semibold tabular-nums">{value}</dd>
    </div>
  )
}
