import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'

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
import { currentYear, type Holiday } from './api'

const LIST = '/schedule/holidays'

/** /schedule/holidays/new va /schedule/holidays/:id/edit */
export function HolidayFormPage() {
  const { id } = useParams()
  const holidayId = id ? Number(id) : null
  const holiday = useQuery({
    queryKey: ['schedule', 'holidays', 'one', holidayId],
    queryFn: () => api<Holiday>(`/api/v1/schedule/holidays/${holidayId}`),
    enabled: holidayId !== null,
    retry: false,
  })
  if (holidayId === null) return <HolidayForm holiday={null} />
  if (holiday.isLoading) return <Skeleton className="mx-auto h-72 max-w-3xl" />
  if (holiday.error instanceof ApiError && holiday.error.status === 404) return <NotFound />
  if (!holiday.data) return null
  return <HolidayForm key={holiday.data.id} holiday={holiday.data} />
}

function HolidayForm({ holiday: h }: { holiday: Holiday | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const manage = useCan()('schedule.manage')
  const [params] = useSearchParams()
  const year = Number(params.get('year')) || currentYear()

  const [name, setName] = useState(h?.name ?? '')
  const [kind, setKind] = useState<'holiday' | 'workday'>(h?.kind ?? 'holiday')
  const [yearly, setYearly] = useState(h?.yearly ?? false)
  const [date, setDate] = useState(h?.date ?? `${year}-01-01`)
  const [note, setNote] = useState(h?.note ?? '')
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const save = useMutation({
    mutationFn: () => {
      const body = { name, kind, yearly, date, note: note || null }
      return h ? send('PUT', `/api/v1/schedule/holidays/${h.id}`, body) : send('POST', '/api/v1/schedule/holidays', body)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['schedule'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(LIST)
    },
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/schedule/holidays/${h?.id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['schedule'] })
      toast.push({ title: t('schedule.holidays.deleted'), tone: 'success' })
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
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={h ? t('schedule.holidays.edit') : t('schedule.holidays.add')} subtitle={h?.name} backTo={LIST} backLabel={t('schedule.holidays.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('schedule.holidays.sectionMain')}>
          <Field label={t('schedule.holidays.name')} error={fe.name}>
            {(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} autoFocus disabled={!manage} />}
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('schedule.holidays.date')} error={fe.date}>
              {(id) => <Input id={id} type="date" value={date} onChange={(e) => setDate(e.target.value)} required disabled={!manage} />}
            </Field>
            <Field label={t('schedule.holidays.kind')} hint={t(`schedule.holidays.kindHint.${kind}`)}>
              {(id) => (
                <Select id={id} value={kind} onChange={(e) => setKind(e.target.value as 'holiday' | 'workday')} disabled={!manage}>
                  <option value="holiday">{t('schedule.holidays.kinds.holiday')}</option>
                  <option value="workday">{t('schedule.holidays.kinds.workday')}</option>
                </Select>
              )}
            </Field>
          </div>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" className="mt-0.5 size-4" checked={yearly} onChange={(e) => setYearly(e.target.checked)} disabled={!manage} />
            <span>
              {t('schedule.holidays.repeatYearly')}
              <span className="block text-xs text-muted">{t('schedule.holidays.repeatHint')}</span>
            </span>
          </label>
          <Field label={t('employees.note')}>
            {(id) => <textarea id={id} value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} rows={3} disabled={!manage} className="w-full rounded-control border border-border bg-surface px-3 py-2 text-sm" />}
          </Field>
        </FormSection>

        {manage && (
          <FormFooter error={save.isError ? errorText(t, save.error) : null}>
            <Button variant="outline" onClick={() => navigate(LIST)}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" disabled={save.isPending || !name.trim() || !date}>
              {t('common.save')}
            </Button>
          </FormFooter>
        )}
      </form>

      {h && manage && (
        <FormSection title={t('org.dangerZone')} danger>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              className="text-danger"
              disabled={remove.isPending}
              onClick={async () => {
                if (await confirm({ title: t('schedule.holidays.delete'), body: t('org.deleteConfirm', { name: h.name }), danger: true, confirmLabel: t('common.delete') })) {
                  setDeleteError(null)
                  remove.mutate()
                }
              }}
            >
              <Trash2 className="size-4" />
              {t('schedule.holidays.delete')}
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
