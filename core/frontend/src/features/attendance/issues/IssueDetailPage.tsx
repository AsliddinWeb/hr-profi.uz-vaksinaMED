import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, X } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'

import { PageHeader } from '../../../components/layout/PageHeader'
import { Badge } from '../../../components/ui/Badge'
import { Button } from '../../../components/ui/Button'
import { Card } from '../../../components/ui/Card'
import { FormSection } from '../../../components/ui/Form'
import { Field } from '../../../components/ui/Input'
import { Skeleton } from '../../../components/ui/Skeleton'
import { useConfirm } from '../../../components/ui/confirmContext'
import { useToast } from '../../../components/ui/toastContext'
import { api, ApiError, send } from '../../../lib/api'
import { formatDate, formatDateTime } from '../../../lib/format'
import { NotFound } from '../../../pages/NotFound'
import { errorText } from '../../auth/errorText'
import { ISSUE_TONE, type AttendanceIssue } from './api'

/** /attendance/issues/:id: tafsilot, tarix, koordinator tasdig'i, HR qarori va bekor qilish. */
export function IssueDetailPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const [note, setNote] = useState('')
  const q = useQuery({ queryKey: ['attendance-issues', 'one', id], queryFn: () => api<AttendanceIssue>(`/api/v1/attendance-issues/${id}`), retry: false })
  const done = (msg: string) => {
    setNote('')
    void qc.invalidateQueries({ queryKey: ['attendance-issues'] })
    void qc.invalidateQueries({ queryKey: ['attendance'] })
    toast.push({ title: msg, tone: 'success' })
  }
  const act = useMutation({
    mutationFn: ({ path, action }: { path: 'verify' | 'decide'; action: 'confirm' | 'reject' | 'approve' }) => send('POST', `/api/v1/attendance-issues/${id}/${path}`, { action, note: note || null }),
    onSuccess: (_r, v) => done(t(v.action === 'reject' ? 'attendance.issue.actions.rejectedMsg' : v.action === 'approve' ? 'attendance.issue.actions.approvedMsg' : 'attendance.issue.actions.verified')),
  })
  const cancel = useMutation({ mutationFn: () => send('POST', `/api/v1/attendance-issues/${id}/cancel`), onSuccess: () => done(t('attendance.issue.actions.cancelledMsg')) })

  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const r = q.data
  if (!r) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  const err = act.isError ? errorText(t, act.error) : cancel.isError ? errorText(t, cancel.error) : null
  const noteMissing = note.trim().length < 1

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <PageHeader title={r.employee.full_name} subtitle={formatDate(r.work_date, i18n.language)} backTo="/attendance/issues" backLabel={t('attendance.issue.back')} />

      <Card className="flex flex-col gap-3 p-6">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={ISSUE_TONE[r.status]}>{t(`attendance.issue.status.${r.status}`)}</Badge>
          <Badge>{t(`attendance.issue.kind.${r.kind}`)}</Badge>
          <Badge>{t(`attendance.issue.method.${r.method_tried}`)}</Badge>
        </div>
        <p className="whitespace-pre-wrap text-sm">{r.comment}</p>
        <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
          {r.branch && <Item label={t('attendance.issue.branch')} value={r.branch} />}
          {r.claimed_in && <Item label={t('attendance.issue.claimedIn')} value={formatDateTime(r.claimed_in, i18n.language)} />}
          {r.claimed_out && <Item label={t('attendance.issue.claimedOut')} value={formatDateTime(r.claimed_out, i18n.language)} />}
          {r.decision_note && <Item label={t('attendance.issue.decisionNote')} value={r.decision_note} />}
        </dl>
      </Card>

      {(r.can_verify || r.can_decide) && (
        <FormSection title={t('attendance.issue.actions.title')}>
          <Field label={t('attendance.issue.actions.note')}>
            {(fid) => <textarea id={fid} value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} rows={3} className="w-full rounded-control border border-border bg-surface px-3 py-2 text-sm" />}
          </Field>
          <div className="flex flex-wrap gap-3">
            {r.can_verify && (
              <Button disabled={act.isPending} onClick={() => act.mutate({ path: 'verify', action: 'confirm' })}>
                <Check className="size-4" />
                {t('attendance.issue.actions.confirm')}
              </Button>
            )}
            {r.can_decide && (
              <Button disabled={act.isPending} onClick={() => act.mutate({ path: 'decide', action: 'approve' })}>
                <Check className="size-4" />
                {t('attendance.issue.actions.approve')}
              </Button>
            )}
            <Button variant="outline" className="text-danger" disabled={act.isPending || noteMissing} onClick={() => act.mutate({ path: r.can_decide ? 'decide' : 'verify', action: 'reject' })}>
              <X className="size-4" />
              {t('attendance.issue.actions.reject')}
            </Button>
            {noteMissing && <span className="self-center text-xs text-muted">{t('attendance.issue.actions.needsNote')}</span>}
          </div>
        </FormSection>
      )}

      {r.can_cancel && (
        <div>
          <Button
            variant="outline"
            className="text-danger"
            disabled={cancel.isPending}
            onClick={async () => {
              if (await confirm({ title: t('attendance.issue.actions.cancel'), body: t('attendance.issue.actions.cancelConfirm'), danger: true, confirmLabel: t('attendance.issue.actions.cancel') })) cancel.mutate()
            }}
          >
            {t('attendance.issue.actions.cancel')}
          </Button>
        </div>
      )}
      {err && (
        <p role="alert" className="text-sm text-danger">
          {err}
        </p>
      )}

      <Card className="p-6">
        <h2 className="font-semibold">{t('attendance.issue.history')}</h2>
        <ol className="mt-4 flex flex-col gap-4 border-l border-border pl-5">
          {r.history.map((e, i) => (
            <li key={i} className="relative">
              <span className="absolute -left-[26px] top-1.5 size-2.5 rounded-full bg-primary" aria-hidden />
              <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
                <span className="font-medium">{t(`attendance.issue.event.${e.action}`)}</span>
                <span className="text-xs text-muted">{formatDateTime(e.at, i18n.language)}</span>
              </div>
              {e.actor && <div className="text-xs text-muted">{e.actor}</div>}
              {e.note && <p className="mt-1 text-sm">{e.note}</p>}
            </li>
          ))}
        </ol>
      </Card>
    </div>
  )
}

function Item({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd>{value}</dd>
    </div>
  )
}
