import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Play, Trash2, X } from 'lucide-react'
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
import { PERIODS, type ReportType, type Run, type Schedule } from './api'

const LIST = '/reports/schedules'
type Rec = { id: number; name: string | null; telegram: boolean }

/** /reports/schedules/new va /reports/schedules/:id/edit */
export function ScheduleFormPage() {
  const { id } = useParams()
  const sid = id ? Number(id) : null
  const q = useQuery({ queryKey: ['reports', 'schedule', sid], queryFn: () => api<Schedule>(`/api/v1/reports/schedules/${sid}`), enabled: sid !== null, retry: false })
  if (sid === null) return <Form s={null} />
  if (q.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!q.data) return null
  return <Form key={q.data.id} s={q.data} />
}

function RecipientPicker({ value, onChange }: { value: Rec[]; onChange: (v: Rec[]) => void }) {
  const { t } = useTranslation()
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const found = useQuery({ queryKey: ['reports', 'users', q], queryFn: () => api<Rec[]>(`/api/v1/reports/users?q=${encodeURIComponent(q.trim())}`) })
  const chosen = new Set(value.map((v) => v.id))
  const options = found.data?.filter((u) => !chosen.has(u.id)) ?? []
  return (
    <div className="flex flex-col gap-2">
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {value.map((v) => (
            <span key={v.id} className="inline-flex items-center gap-1.5 rounded-full bg-surface-2 px-2.5 py-1 text-sm">
              {v.name}
              {v.telegram && <span className="text-[10px] text-muted">TG</span>}
              <button type="button" onClick={() => onChange(value.filter((x) => x.id !== v.id))} aria-label={t('common.clear')} className="text-muted hover:text-text">
                <X className="size-3.5" />
              </button>
            </span>
          ))}
        </div>
      )}
      <div className="relative">
        <Input value={q} onChange={(e) => setQ(e.target.value)} onFocus={() => setOpen(true)} onBlur={() => setOpen(false)} placeholder={t('tasks.form.searchPerson')} autoComplete="off" aria-label={t('reports.schedules.recipients')} />
        {open && options.length > 0 && (
          <ul className="absolute z-20 mt-1 max-h-56 w-full overflow-auto rounded-control border border-border bg-surface py-1 shadow-card" role="listbox">
            {options.map((u) => (
              <li key={u.id} role="option" aria-selected={false}>
                <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => (onChange([...value, u]), setQ(''))} className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-surface-2">
                  {u.name}
                  {u.telegram && <span className="text-[10px] text-muted">TG</span>}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

function Form({ s }: { s: Schedule | null }) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const types = useQuery({ queryKey: ['reports', 'types'], queryFn: () => api<{ types: ReportType[] }>('/api/v1/reports/types') })
  const [name, setName] = useState(s?.name ?? '')
  const [rtype, setRtype] = useState(s?.report_type ?? '')
  const [period, setPeriod] = useState<string>(s?.period ?? 'last_week')
  const [format, setFormat] = useState(s?.format ?? 'xlsx')
  const [lang, setLang] = useState(s?.lang ?? (i18n.language === 'ru' ? 'ru' : 'uz'))
  const [frequency, setFrequency] = useState(s?.frequency ?? 'weekly')
  const [time, setTime] = useState(`${String(s?.hour ?? 8).padStart(2, '0')}:${String(s?.minute ?? 0).padStart(2, '0')}`)
  const [weekday, setWeekday] = useState(String(s?.weekday ?? 0))
  const [monthDay, setMonthDay] = useState(String(s?.month_day ?? 1))
  const [recipients, setRecipients] = useState<Rec[]>(s?.recipients ?? [])
  const [channels, setChannels] = useState<string[]>(s?.channels ?? ['app'])
  const [active, setActive] = useState(s?.is_active ?? true)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const current = types.data?.types.find((x) => x.type === (rtype || types.data.types[0]?.type))
  const [hh, mm] = time.split(':').map(Number)

  const save = useMutation({
    mutationFn: () => {
      const body = {
        name, report_type: current?.type, period, format, lang, frequency, hour: hh || 0, minute: mm || 0, weekday: frequency === 'weekly' ? Number(weekday) : null,
        month_day: frequency === 'monthly' ? Number(monthDay) : null, recipient_ids: recipients.map((r) => r.id), channels, is_active: active,
      }
      return s ? send<Schedule>('PUT', `/api/v1/reports/schedules/${s.id}`, body) : send<Schedule>('POST', '/api/v1/reports/schedules', body)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['reports'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(LIST)
    },
  })
  const runNow = useMutation({
    mutationFn: () => send<Run>('POST', `/api/v1/reports/schedules/${s?.id}/run`, {}),
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['reports'] })
      toast.push({ title: r.status === 'ok' ? t('reports.schedules.ranOk') : t('reports.failed'), tone: r.status === 'ok' ? 'success' : 'danger' })
    },
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/reports/schedules/${s?.id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['reports'] })
      toast.push({ title: t('reports.schedules.deleted'), tone: 'success' })
      navigate(LIST)
    },
    onError: (e) => setDeleteError(errorText(t, e)),
  })
  const fe = save.isError ? fieldErrors(t, save.error) : {}
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  const toggleChannel = (c: string) => setChannels((cur) => (cur.includes(c) ? cur.filter((x) => x !== c) : [...cur, c]))
  const noTg = channels.includes('telegram') && recipients.some((r) => !r.telegram)

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={s ? t('reports.schedules.edit') : t('reports.schedules.add')} subtitle={s?.name} backTo={LIST} backLabel={t('reports.schedules.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('reports.schedules.reportSection')}>
          <Field label={t('reports.schedules.name')} error={fe.name}>{(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} required maxLength={160} autoFocus />}</Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('reports.report')}>
              {(id) => (
                <Select id={id} value={current?.type ?? ''} onChange={(e) => setRtype(e.target.value)}>
                  {types.data?.types.map((x) => (
                    <option key={x.type} value={x.type}>
                      {x.title[i18n.language === 'ru' ? 'ru' : 'uz']}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            {current?.needs_period && (
              <Field label={t('reports.periodCol')}>
                {(id) => (
                  <Select id={id} value={period} onChange={(e) => setPeriod(e.target.value)}>
                    {PERIODS.map((p) => (
                      <option key={p} value={p}>
                        {t(`reports.period.${p}`)}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            )}
            <Field label={t('reports.format')}>
              {(id) => (
                <Select id={id} value={format} onChange={(e) => setFormat(e.target.value as 'xlsx' | 'pdf')}>
                  <option value="xlsx">Excel (.xlsx)</option>
                  <option value="pdf">PDF</option>
                </Select>
              )}
            </Field>
            <Field label={t('reports.lang')}>
              {(id) => (
                <Select id={id} value={lang} onChange={(e) => setLang(e.target.value as 'uz' | 'ru')}>
                  <option value="uz">O‘zbekcha</option>
                  <option value="ru">Русский</option>
                </Select>
              )}
            </Field>
          </div>
        </FormSection>
        <FormSection title={t('reports.schedules.when')}>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={t('reports.schedules.frequency')}>
              {(id) => (
                <Select id={id} value={frequency} onChange={(e) => setFrequency(e.target.value as 'daily' | 'weekly' | 'monthly')}>
                  {(['daily', 'weekly', 'monthly'] as const).map((f) => (
                    <option key={f} value={f}>
                      {t(`reports.frequency.${f}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            {frequency === 'weekly' && (
              <Field label={t('reports.schedules.weekday')}>
                {(id) => (
                  <Select id={id} value={weekday} onChange={(e) => setWeekday(e.target.value)}>
                    {[0, 1, 2, 3, 4, 5, 6].map((d) => (
                      <option key={d} value={d}>
                        {t(`reports.weekday.${d}`)}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            )}
            {frequency === 'monthly' && (
              <Field label={t('reports.schedules.monthDay')} hint={t('reports.schedules.monthDayHint')}>{(id) => <Input id={id} type="number" min={1} max={28} value={monthDay} onChange={(e) => setMonthDay(e.target.value)} />}</Field>
            )}
            <Field label={t('reports.schedules.time')}>{(id) => <Input id={id} type="time" value={time} onChange={(e) => setTime(e.target.value)} required />}</Field>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4" checked={active} onChange={(e) => setActive(e.target.checked)} />
            {t('reports.schedules.active')}
          </label>
        </FormSection>
        <FormSection title={t('reports.schedules.recipients')} description={t('reports.schedules.recipientsHint')}>
          <Field label={t('reports.schedules.recipients')} error={fe.recipient_ids}>{() => <RecipientPicker value={recipients} onChange={setRecipients} />}</Field>
          <div className="flex flex-wrap gap-4">
            {(['app', 'telegram'] as const).map((c) => (
              <label key={c} className="flex items-center gap-2 text-sm">
                <input type="checkbox" className="size-4" checked={channels.includes(c)} onChange={() => toggleChannel(c)} />
                {t(`reports.channel.${c}`)}
              </label>
            ))}
          </div>
          {channels.length === 0 && <p role="alert" className="text-sm text-danger">{t('reports.schedules.noChannel')}</p>}
          {noTg && <p className="text-xs text-muted">{t('reports.schedules.noTelegram')}</p>}
        </FormSection>
        <FormFooter error={save.isError && !Object.keys(fe).length ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(LIST)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !name.trim() || recipients.length === 0 || channels.length === 0 || !current}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
      {s && (
        <FormSection title={t('reports.schedules.actions')} description={t('reports.schedules.runHint')}>
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="outline" disabled={runNow.isPending} onClick={() => runNow.mutate()}>
              <Play className="size-4" />
              {t('reports.schedules.runNow')}
            </Button>
            {runNow.isError && <span role="alert" className="text-sm text-danger">{errorText(t, runNow.error)}</span>}
          </div>
        </FormSection>
      )}
      {s && (
        <FormSection title={t('org.dangerZone')} danger>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              className="text-danger"
              disabled={remove.isPending}
              onClick={async () => {
                if (await confirm({ title: t('reports.schedules.delete'), body: t('org.deleteConfirm', { name: s.name }), danger: true, confirmLabel: t('common.delete') })) {
                  setDeleteError(null)
                  remove.mutate()
                }
              }}
            >
              <Trash2 className="size-4" />
              {t('reports.schedules.delete')}
            </Button>
            {deleteError && <span role="alert" className="text-sm text-danger">{deleteError}</span>}
          </div>
        </FormSection>
      )}
    </div>
  )
}
