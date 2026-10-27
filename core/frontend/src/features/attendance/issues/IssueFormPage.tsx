import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { PageHeader } from '../../../components/layout/PageHeader'
import { Button } from '../../../components/ui/Button'
import { FormFooter, FormSection } from '../../../components/ui/Form'
import { Field, Input, Select } from '../../../components/ui/Input'
import { useToast } from '../../../components/ui/toastContext'
import { send } from '../../../lib/api'
import { errorText, fieldErrors } from '../../auth/errorText'
import { addDays, fromLocalInput, todayLocal } from '../api'
import { ISSUE_KINDS, ISSUE_METHODS, type AttendanceIssue } from './api'

/** /attendance/issues/new: belgilash o'tmagan yoki noto'g'ri yozilgan holat haqida so'rov. */
export function IssueFormPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [params] = useSearchParams()
  const [today] = useState(todayLocal)
  const [date, setDate] = useState(today)
  const [kind, setKind] = useState<string>('missed_in')
  const [method, setMethod] = useState<string>(params.get('method') ?? 'qr')
  const [inAt, setInAt] = useState('')
  const [outAt, setOutAt] = useState('')
  const [comment, setComment] = useState('')

  const save = useMutation({
    mutationFn: () =>
      send<AttendanceIssue>('POST', '/api/v1/attendance-issues', {
        work_date: date, kind, method_tried: method, claimed_in: fromLocalInput(inAt), claimed_out: fromLocalInput(outAt), comment,
      }), // fmt: skip
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['attendance-issues'] })
      toast.push({ title: t('attendance.issue.form.sent'), tone: 'success' })
      navigate(`/attendance/issues/${r.id}`, { replace: true })
    },
  })
  const fe = save.isError ? fieldErrors(t, save.error) : {}
  const needsTime = kind === 'missed_in' || kind === 'missed_out'
  const valid = comment.trim().length >= 3 && (!needsTime || !!inAt || !!outAt) && (!inAt || !outAt || outAt > inAt)
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={t('attendance.issue.new')} subtitle={t('attendance.issue.form.subtitle')} backTo="/attendance" backLabel={t('attendance.my.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('attendance.issue.form.what')}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('attendance.issue.form.date')} error={fe.work_date}>
              {(id) => <Input id={id} type="date" value={date} min={addDays(today, -14)} max={today} onChange={(e) => setDate(e.target.value)} required />}
            </Field>
            <Field label={t('attendance.issue.form.method')}>
              {(id) => (
                <Select id={id} value={method} onChange={(e) => setMethod(e.target.value)}>
                  {ISSUE_METHODS.map((m) => (
                    <option key={m} value={m}>
                      {t(`attendance.issue.method.${m}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
          <div className="grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label={t('attendance.issue.form.what')}>
            {ISSUE_KINDS.map((k) => (
              <button key={k} type="button" role="radio" aria-checked={kind === k} onClick={() => setKind(k)} className={'rounded-control border px-4 py-3 text-left text-sm ' + (kind === k ? 'border-primary bg-primary/10 font-medium' : 'border-border hover:bg-surface-2')}>
                {t(`attendance.issue.kind.${k}`)}
              </button>
            ))}
          </div>
        </FormSection>

        <FormSection title={t('attendance.issue.form.when')}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('attendance.issue.form.claimedIn')} error={fe.claimed_in}>
              {(id) => <Input id={id} type="datetime-local" value={inAt} onChange={(e) => setInAt(e.target.value)} />}
            </Field>
            <Field label={t('attendance.issue.form.claimedOut')} error={inAt && outAt && outAt <= inAt ? t('errors.out_before_in') : fe.claimed_out}>
              {(id) => <Input id={id} type="datetime-local" value={outAt} onChange={(e) => setOutAt(e.target.value)} />}
            </Field>
          </div>
        </FormSection>

        <FormSection title={t('attendance.issue.form.comment')}>
          <Field label={t('attendance.issue.form.comment')} hint={t('attendance.issue.form.commentHint')} error={fe.comment}>
            {(id) => <textarea id={id} value={comment} onChange={(e) => setComment(e.target.value)} maxLength={1000} rows={4} className="w-full rounded-control border border-border bg-surface px-3 py-2 text-sm" />}
          </Field>
        </FormSection>

        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate('/attendance')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !valid}>
            {t('attendance.issue.form.submit')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
