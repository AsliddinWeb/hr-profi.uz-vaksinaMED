import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { fromLocalInput, toLocalInput } from '../attendance/api'
import { errorText, fieldErrors } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import { NotFound } from '../../pages/NotFound'
import { WeekdayPicker } from '../schedule/WeekdayPicker'
import { PersonPicker } from '../tasks/PersonPicker'
import type { Person } from '../tasks/api'
import { REPEATS, whenText, type ReminderDetail } from './api'

/** /reminders/new va /reminders/:id/edit */
export function FormPage() {
  const { id } = useParams()
  const rid = id ? Number(id) : null
  const rem = useQuery({ queryKey: ['reminders', 'one', rid], queryFn: () => api<ReminderDetail>(`/api/v1/reminders/${rid}`), enabled: rid !== null, retry: false })
  if (rid === null) return <ReminderForm rem={null} />
  if (rem.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if ((rem.error instanceof ApiError && rem.error.status === 404) || (rem.data && !rem.data.is_owner)) return <NotFound />
  if (!rem.data) return null
  return <ReminderForm key={rem.data.id} rem={rem.data} />
}

function defaultStart(): string {
  const d = new Date(Date.now() + 60 * 60 * 1000)
  d.setMinutes(0, 0, 0)
  return toLocalInput(d.toISOString())
}

function ReminderForm({ rem }: { rem: ReminderDetail | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const can = useCan()
  const [params] = useSearchParams()
  const [title, setTitle] = useState(rem?.title ?? params.get('title') ?? '')
  const [note, setNote] = useState(rem?.note ?? '')
  const [link, setLink] = useState(rem?.link ?? params.get('link') ?? '')
  const [start, setStart] = useState(() => (rem ? toLocalInput(rem.first_at) : defaultStart()))
  const [repeat, setRepeat] = useState<string>(rem?.repeat ?? 'once')
  const [interval, setIntervalN] = useState(String(rem?.interval ?? 1))
  const [weekdays, setWeekdays] = useState<number[]>(rem?.weekdays ?? [])
  const [until, setUntil] = useState(rem?.until ?? '')
  const [telegram, setTelegram] = useState(rem?.telegram ?? true)
  const [recipients, setRecipients] = useState<Person[]>(rem?.recipients ?? [])

  const body = {
    title, note: note || null, link: link || null, first_at: fromLocalInput(start), repeat, interval: Number(interval) || 1,
    weekdays: repeat === 'weekly' ? weekdays : [], until: until || null, recipients: recipients.map((r) => r.id), telegram,
  } // fmt: skip
  const [preview, setPreview] = useState<string[]>([])
  const previewKey = JSON.stringify([body.first_at, body.repeat, body.interval, body.weekdays, body.until])
  useEffect(() => {
    if (!body.first_at) return
    const timer = setTimeout(() => {
      api<{ next: string[] }>('/api/v1/reminders/preview', { method: 'POST', body: JSON.stringify({ ...body, title: title || '—' }) })
        .then((r) => setPreview(r.next))
        .catch(() => setPreview([]))
    }, 400)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previewKey])

  const save = useMutation({
    mutationFn: () => (rem ? send<ReminderDetail>('PUT', `/api/v1/reminders/${rem.id}`, body) : send<ReminderDetail>('POST', '/api/v1/reminders', body)),
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['reminders'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(`/reminders/${r.id}`, { replace: true })
    },
  })
  const fe = save.isError ? fieldErrors(t, save.error) : {}
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  const back = rem ? `/reminders/${rem.id}` : '/reminders'

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={rem ? t('reminders.edit') : t('reminders.new')} subtitle={rem?.title} backTo={back} backLabel={rem ? rem.title : t('reminders.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('reminders.form.what')}>
          <Field label={t('reminders.form.title')} error={fe.title}>{(id) => <Input id={id} value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={200} autoFocus />}</Field>
          <Field label={t('reminders.form.note')}>{(id) => <textarea id={id} value={note} onChange={(e) => setNote(e.target.value)} rows={3} maxLength={2000} className="w-full rounded-control border border-border bg-surface px-3 py-2 text-sm" />}</Field>
          <Field label={t('reminders.form.link')} hint={t('reminders.form.linkHint')} error={fe.link ? t('reminders.form.linkInvalid') : null}>
            {(id) => <Input id={id} value={link} onChange={(e) => setLink(e.target.value)} placeholder="/tasks/5" maxLength={300} />}
          </Field>
        </FormSection>

        <FormSection title={t('reminders.form.when')} description={t('reminders.form.whenHint')}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('reminders.form.start')}>{(id) => <Input id={id} type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} required />}</Field>
            <Field label={t('reminders.form.repeat')}>
              {(id) => (
                <Select id={id} value={repeat} onChange={(e) => setRepeat(e.target.value)}>
                  {REPEATS.map((r) => (
                    <option key={r} value={r}>
                      {t(`reminders.repeat.${r}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
          {repeat !== 'once' && (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t('reminders.form.every')} hint={t(`reminders.form.unit.${repeat}`)}>
                {(id) => <Input id={id} type="number" min={1} max={52} value={interval} onChange={(e) => setIntervalN(e.target.value)} />}
              </Field>
              <Field label={t('reminders.form.untilLabel')} hint={t('reminders.form.untilHint')} error={fe.until}>
                {(id) => <Input id={id} type="date" value={until} onChange={(e) => setUntil(e.target.value)} />}
              </Field>
            </div>
          )}
          {repeat === 'weekly' && (
            <div className="flex flex-col gap-2">
              <span className="text-sm font-medium">{t('reminders.form.weekdays')}</span>
              <WeekdayPicker value={weekdays} onChange={setWeekdays} label={t('reminders.form.weekdays')} />
              <p className="text-xs text-muted">{t('reminders.form.weekdaysHint')}</p>
            </div>
          )}
          <div className="rounded-control bg-surface-2 p-3 text-sm" aria-live="polite">
            <div className="text-xs text-muted">{t('reminders.form.preview')}</div>
            {preview.length ? (
              <ul className="mt-1 flex flex-wrap gap-x-5 gap-y-1 tabular-nums">
                {preview.map((p) => (
                  <li key={p}>{whenText(p)}</li>
                ))}
              </ul>
            ) : (
              <p className="mt-1 text-muted">{t('reminders.form.noPreview')}</p>
            )}
          </div>
        </FormSection>

        <FormSection title={t('reminders.form.delivery')}>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" className="mt-0.5 size-4" checked={telegram} onChange={(e) => setTelegram(e.target.checked)} />
            <span>
              {t('reminders.form.telegram')}
              <span className="block text-xs text-muted">{t('reminders.form.telegramHint')}</span>
            </span>
          </label>
          {can('reminders.assign') && (
            <Field label={t('reminders.form.recipients')} hint={t('reminders.form.recipientsHint')}>{(id) => <PersonPicker id={id} value={recipients} onChange={setRecipients} multiple max={20} />}</Field>
          )}
        </FormSection>

        <FormFooter error={save.isError && !Object.keys(fe).length ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(back)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !title.trim() || !start}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
