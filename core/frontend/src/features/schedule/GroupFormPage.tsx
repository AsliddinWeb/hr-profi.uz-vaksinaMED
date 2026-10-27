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
import { CATEGORIES, type Category, type Shift, type WorkGroup } from './api'
import { WeekdayPicker } from './WeekdayPicker'

const LIST = '/schedule/groups'

/** Kategoriya bo'yicha tavsiya etilgan qoidalar (yangi guruh yaratishda formaga tushadi). */
const PRESETS: Record<Category, { off: number[]; holidays: boolean; attendance: boolean }> = {
  office: { off: [6], holidays: true, attendance: true },
  pharmacy: { off: [], holidays: false, attendance: true },
  warehouse: { off: [6], holidays: true, attendance: true },
  security: { off: [], holidays: false, attendance: true },
  other: { off: [6], holidays: true, attendance: true },
}

/** /schedule/groups/new va /schedule/groups/:id/edit */
export function GroupFormPage() {
  const { id } = useParams()
  const groupId = id ? Number(id) : null
  const group = useQuery({
    queryKey: ['schedule', 'groups', groupId],
    queryFn: () => api<WorkGroup>(`/api/v1/schedule/groups/${groupId}`),
    enabled: groupId !== null,
    retry: false,
  })
  if (groupId === null) return <GroupForm group={null} />
  if (group.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (group.error instanceof ApiError && group.error.status === 404) return <NotFound />
  if (!group.data) return null
  return <GroupForm key={group.data.id} group={group.data} />
}

function GroupForm({ group: g }: { group: WorkGroup | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const manage = useCan()('schedule.manage')

  const [name, setName] = useState(g?.name ?? '')
  const [category, setCategory] = useState<Category>(g?.category ?? 'office')
  const [description, setDescription] = useState(g?.description ?? '')
  const [shiftId, setShiftId] = useState(g?.default_shift_id?.toString() ?? '')
  const [off, setOff] = useState<number[]>(g?.weekly_off_days ?? PRESETS.office.off)
  const [holidays, setHolidays] = useState(g?.observe_holidays ?? true)
  const [attendance, setAttendance] = useState(g?.attendance_required ?? true)
  const [isDefault, setIsDefault] = useState(g?.is_default ?? false)
  const [sort, setSort] = useState(String(g?.sort_order ?? 0))
  const [active, setActive] = useState(g?.is_active ?? true)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const shifts = useQuery({ queryKey: ['schedule', 'shifts'], queryFn: () => api<Shift[]>('/api/v1/schedule/shifts') })

  const pickCategory = (c: Category) => {
    setCategory(c)
    if (!g) {
      setOff(PRESETS[c].off)
      setHolidays(PRESETS[c].holidays)
      setAttendance(PRESETS[c].attendance)
    }
  }

  const save = useMutation({
    mutationFn: () => {
      const body = {
        name,
        category,
        description: description || null,
        default_shift_id: shiftId ? Number(shiftId) : null,
        weekly_off_days: off,
        observe_holidays: holidays,
        attendance_required: attendance,
        is_default: isDefault,
        sort_order: Number(sort) || 0,
        is_active: active,
      }
      return g ? send('PUT', `/api/v1/schedule/groups/${g.id}`, body) : send('POST', '/api/v1/schedule/groups', body)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['schedule'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(LIST)
    },
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/schedule/groups/${g?.id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['schedule'] })
      toast.push({ title: t('schedule.groups.deleted'), tone: 'success' })
      navigate(LIST)
    },
    onError: (e) => setDeleteError(errorText(t, e)),
  })

  const fe = save.isError ? fieldErrors(t, save.error) : {}
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={g ? t('schedule.groups.edit') : t('schedule.groups.add')} subtitle={g?.name} backTo={LIST} backLabel={t('schedule.groups.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('schedule.groups.sectionMain')}>
          <Field label={t('schedule.groups.name')} error={fe.name}>
            {(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} required maxLength={80} autoFocus disabled={!manage} />}
          </Field>
          <Field label={t('schedule.groups.category')} hint={g ? undefined : t('schedule.groups.categoryHint')}>
            {(id) => (
              <Select id={id} value={category} onChange={(e) => pickCategory(e.target.value as Category)} disabled={!manage}>
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {t(`schedule.categories.${c}`)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label={t('schedule.groups.description')}>
            {(id) => <Input id={id} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={300} disabled={!manage} />}
          </Field>
        </FormSection>

        <FormSection title={t('schedule.groups.sectionRules')} description={t('schedule.groups.rulesHint')}>
          <Field label={t('schedule.groups.defaultShift')} hint={t('schedule.groups.defaultShiftHint')}>
            {(id) => (
              <Select id={id} value={shiftId} onChange={(e) => setShiftId(e.target.value)} disabled={!manage}>
                <option value="">{t('schedule.groups.noShift')}</option>
                {shifts.data
                  ?.filter((s) => s.is_active || String(s.id) === shiftId)
                  .map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} · {s.start_time}–{s.end_time}
                    </option>
                  ))}
              </Select>
            )}
          </Field>
          <div className="flex flex-col gap-2">
            <span className="text-sm font-medium">{t('schedule.groups.weeklyOff')}</span>
            <WeekdayPicker value={off} onChange={setOff} disabled={!manage} label={t('schedule.groups.weeklyOff')} />
            {fe.weekly_off_days && <p role="alert" className="text-xs text-danger">{fe.weekly_off_days}</p>}
          </div>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" className="mt-0.5 size-4" checked={holidays} onChange={(e) => setHolidays(e.target.checked)} disabled={!manage} />
            <span>
              {t('schedule.groups.observeHolidays')}
              <span className="block text-xs text-muted">{t('schedule.groups.observeHolidaysHint')}</span>
            </span>
          </label>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" className="mt-0.5 size-4" checked={attendance} onChange={(e) => setAttendance(e.target.checked)} disabled={!manage} />
            <span>
              {t('schedule.groups.attendanceRequired')}
              <span className="block text-xs text-muted">{t('schedule.groups.attendanceHint')}</span>
            </span>
          </label>
        </FormSection>

        <FormSection title={t('schedule.groups.sectionStatus')}>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" className="mt-0.5 size-4" checked={isDefault} onChange={(e) => setIsDefault(e.target.checked)} disabled={!manage || g?.is_default} />
            <span>
              {t('schedule.groups.makeDefault')}
              <span className="block text-xs text-muted">{t('schedule.groups.defaultHint')}</span>
            </span>
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('schedule.sort')}>{(id) => <Input id={id} type="number" value={sort} onChange={(e) => setSort(e.target.value)} disabled={!manage} />}</Field>
          </div>
          {g && (
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
            <Button type="submit" disabled={save.isPending || !name.trim() || off.length > 6}>
              {t('common.save')}
            </Button>
          </FormFooter>
        )}
      </form>

      {g && manage && (
        <FormSection title={t('org.dangerZone')} description={t('schedule.groups.deleteHint')} danger>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              className="text-danger"
              disabled={remove.isPending}
              onClick={async () => {
                if (await confirm({ title: t('schedule.groups.delete'), body: t('org.deleteConfirm', { name: g.name }), danger: true, confirmLabel: t('common.delete') })) {
                  setDeleteError(null)
                  remove.mutate()
                }
              }}
            >
              <Trash2 className="size-4" />
              {t('schedule.groups.delete')}
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
