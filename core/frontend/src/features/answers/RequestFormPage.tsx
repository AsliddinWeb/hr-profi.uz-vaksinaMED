import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { useToast } from '../../components/ui/toastContext'
import { ApiError, send } from '../../lib/api'
import { addDays, todayLocal } from '../attendance/api'
import { errorText, fieldErrors } from '../auth/errorText'
import { REASONS, type Kind, type LeaveRequest } from './api'

/** /answers/new: kunlik yoki soatlik ruxsat so'rovi. */
export function RequestFormPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [today] = useState(todayLocal)
  const [kind, setKind] = useState<Kind>('day')
  const [reasonType, setReasonType] = useState<string>('personal')
  const [reason, setReason] = useState('')
  const [start, setStart] = useState(today)
  const [end, setEnd] = useState(today)
  const [from, setFrom] = useState('15:00')
  const [to, setTo] = useState('17:00')

  const save = useMutation({
    mutationFn: () =>
      send<LeaveRequest>('POST', '/api/v1/answers/requests', {
        kind, reason_type: reasonType, reason: reason || null, start_date: start,
        end_date: kind === 'day' ? end : start, start_time: kind === 'hourly' ? from : null, end_time: kind === 'hourly' ? to : null,
      }), // fmt: skip
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['answers'] })
      toast.push({ title: t('answers.form.sent'), tone: 'success' })
      navigate(`/answers/${r.id}`, { replace: true })
    },
  })
  const fe = save.isError ? fieldErrors(t, save.error) : {}
  const error = save.error instanceof ApiError && save.error.code !== 'validation' ? answersError(t, save.error) : save.isError ? errorText(t, save.error) : null
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  const valid = kind === 'day' ? !!start && end >= start : !!start && !!from && !!to && to > from && (reasonType !== 'other' || reason.trim().length >= 3)

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={t('answers.new')} subtitle={t('answers.form.subtitle')} backTo="/answers" backLabel={t('answers.my.title')} />
      <Card className="flex flex-col gap-2 p-5">
        <h2 className="font-semibold">{t('answers.form.rulesTitle')}</h2>
        <ol className="list-decimal pl-5 text-sm text-muted">
          {[1, 2, 3, 4].map((n) => (
            <li key={n}>{t(`answers.form.rules.${n}`)}</li>
          ))}
        </ol>
      </Card>
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('answers.form.kind')}>
          <div className="grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label={t('answers.form.kind')}>
            {(['day', 'hourly'] as const).map((k) => (
              <button key={k} type="button" role="radio" aria-checked={kind === k} onClick={() => setKind(k)} className={'rounded-control border px-4 py-3 text-left text-sm ' + (kind === k ? 'border-primary bg-primary/10 font-medium' : 'border-border hover:bg-surface-2')}>
                {t(`answers.kind.${k}`)}
                <span className="mt-0.5 block text-xs font-normal text-muted">{t(`answers.kindHint.${k}`)}</span>
              </button>
            ))}
          </div>
        </FormSection>

        <FormSection title={t('answers.form.when')}>
          {kind === 'day' ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t('schedule.apply.from')} error={fe.start_date}>
                {(id) => <Input id={id} type="date" value={start} min={addDays(today, -7)} onChange={(e) => (setStart(e.target.value), end < e.target.value && setEnd(e.target.value))} required />}
              </Field>
              <Field label={t('schedule.apply.to')} error={end < start ? t('errors.range_invalid') : null}>
                {(id) => <Input id={id} type="date" value={end} min={start} onChange={(e) => setEnd(e.target.value)} required />}
              </Field>
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label={t('attendance.date')}>{(id) => <Input id={id} type="date" value={start} min={addDays(today, -7)} onChange={(e) => setStart(e.target.value)} required />}</Field>
              <Field label={t('answers.form.from')}>{(id) => <Input id={id} type="time" value={from} onChange={(e) => setFrom(e.target.value)} required />}</Field>
              <Field label={t('answers.form.to')} error={to <= from ? t('errors.time_invalid') : null}>
                {(id) => <Input id={id} type="time" value={to} onChange={(e) => setTo(e.target.value)} required />}
              </Field>
            </div>
          )}
        </FormSection>

        <FormSection title={t('answers.form.why')} description={t('answers.form.route')}>
          <Field label={t('answers.reasonType')}>
            {(id) => (
              <Select id={id} value={reasonType} onChange={(e) => setReasonType(e.target.value)}>
                {REASONS.map((r) => (
                  <option key={r} value={r}>
                    {t(`answers.reason.${r}`)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label={t('answers.form.note')} hint={reasonType === 'other' ? t('answers.form.noteRequired') : undefined} error={fe.reason}>
            {(id) => <textarea id={id} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={1000} rows={4} className="w-full rounded-control border border-border bg-surface px-3 py-2 text-sm" />}
          </Field>
        </FormSection>

        <FormFooter error={error}>
          <Button variant="outline" onClick={() => navigate('/answers')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !valid}>
            {t('answers.form.submit')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}

function answersError(t: (k: string, o?: Record<string, unknown>) => string, e: ApiError): string {
  const key = `errors.${e.code}`
  const text = t(key, e.extra as Record<string, unknown>)
  return text === key ? t('errors.unknown') : text
}
