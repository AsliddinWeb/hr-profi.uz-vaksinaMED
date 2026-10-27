import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, X } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { FormSection } from '../../components/ui/Form'
import { Field } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { period, STATUS_TONE, type LeaveDetail } from './api'

/** /answers/:id: so'rov tafsiloti, tarix (timeline), qaror (tasdiq/rad) va bekor qilish. */
export function RequestDetailPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const [note, setNote] = useState('')
  const q = useQuery({ queryKey: ['answers', 'one', id], queryFn: () => api<LeaveDetail>(`/api/v1/answers/requests/${id}`), retry: false })
  const done = (msg: string) => {
    void qc.invalidateQueries({ queryKey: ['answers'] })
    toast.push({ title: msg, tone: 'success' })
  }
  const decide = useMutation({
    mutationFn: (action: 'approve' | 'reject') => send('POST', `/api/v1/answers/requests/${id}/decision`, { action, note: note || null }),
    onSuccess: (_r, action) => (setNote(''), done(action === 'approve' ? t('answers.decision.approved') : t('answers.decision.rejected'))),
  })
  const cancel = useMutation({ mutationFn: () => send('POST', `/api/v1/answers/requests/${id}/cancel`), onSuccess: () => done(t('answers.cancelled')) })

  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const r = q.data
  if (!r) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  const err = decide.isError ? errorText(t, decide.error) : cancel.isError ? errorText(t, cancel.error) : null

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <PageHeader title={r.employee.full_name} subtitle={period(r)} backTo={r.can_decide ? '/answers/inbox' : '/answers'} backLabel={t('answers.back')} />

      <Card className="flex flex-col gap-3 p-6">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={STATUS_TONE[r.status]}>{t(`answers.status.${r.status}`)}</Badge>
          <Badge>{t(`answers.kind.${r.kind}`)}</Badge>
          <Badge>{t(`answers.reason.${r.reason_type}`)}</Badge>
        </div>
        {r.reason && <p className="whitespace-pre-wrap text-sm">{r.reason}</p>}
        <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
          <Item label={t('answers.submitted')} value={formatDateTime(r.submitted_at, i18n.language)} />
          <Item label={t('answers.coordinator')} value={r.coordinator ?? t('answers.noCoordinator')} />
          {r.status === 'pending_coordinator' && r.escalate_at && <Item label={t('answers.escalatesAt')} value={formatDateTime(r.escalate_at, i18n.language)} />}
          {r.decided_at && <Item label={t('answers.decidedAt')} value={`${formatDateTime(r.decided_at, i18n.language)} · ${t(`answers.level.${r.decided_level}`)}`} />}
          {r.decision_note && <Item label={t('answers.decisionNote')} value={r.decision_note} />}
        </dl>
      </Card>

      {r.can_decide && (
        <FormSection title={t('answers.decision.title')} description={t('answers.decision.hint')}>
          <Field label={t('answers.decision.note')}>
            {(fid) => <textarea id={fid} value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} rows={3} className="w-full rounded-control border border-border bg-surface px-3 py-2 text-sm" />}
          </Field>
          <div className="flex flex-wrap gap-3">
            <Button disabled={decide.isPending} onClick={() => decide.mutate('approve')}>
              <Check className="size-4" />
              {t('answers.decision.approve')}
            </Button>
            <Button variant="outline" className="text-danger" disabled={decide.isPending || note.trim().length < 1} onClick={() => decide.mutate('reject')}>
              <X className="size-4" />
              {t('answers.decision.reject')}
            </Button>
            {note.trim().length < 1 && <span className="self-center text-xs text-muted">{t('answers.decision.rejectNeedsNote')}</span>}
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
              if (await confirm({ title: t('answers.cancel'), body: t('answers.cancelConfirm'), danger: true, confirmLabel: t('answers.cancel') })) cancel.mutate()
            }}
          >
            {t('answers.cancel')}
          </Button>
        </div>
      )}
      {err && (
        <p role="alert" className="text-sm text-danger">
          {err}
        </p>
      )}

      <Card className="p-6">
        <h2 className="font-semibold">{t('answers.history')}</h2>
        <ol className="mt-4 flex flex-col gap-4 border-l border-border pl-5">
          {r.events.map((e) => (
            <li key={e.id} className="relative">
              <span className="absolute -left-[26px] top-1.5 size-2.5 rounded-full bg-primary" aria-hidden />
              <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
                <span className="font-medium">
                  {t(`answers.event.${e.action}`)}
                  {e.level && e.action !== 'cancelled' && <span className="ml-1.5 font-normal text-muted">({t(`answers.level.${e.level}`)})</span>}
                </span>
                <span className="text-xs text-muted">{formatDateTime(e.created_at, i18n.language)}</span>
              </div>
              {e.actor && <div className="text-xs text-muted">{e.actor}</div>}
              {e.note && e.action !== 'escalated' && <p className="mt-1 text-sm">{e.note}</p>}
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
