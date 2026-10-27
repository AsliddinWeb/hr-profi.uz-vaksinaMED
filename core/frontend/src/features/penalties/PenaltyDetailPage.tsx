import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, FileWarning, X } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { FormSection } from '../../components/ui/Form'
import { Field } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { formatDate, formatDateTime } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { money, TONE, type PenaltyDetail } from './api'

/** /penalties/:id: jarima tafsiloti, qoida versiyasi, tushuntirish xatlari, tasdiqlash yoki bekor qilish. */
export function PenaltyDetailPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const qc = useQueryClient()
  const toast = useToast()
  const [note, setNote] = useState('')
  const q = useQuery({ queryKey: ['penalties', 'one', id], queryFn: () => api<PenaltyDetail>(`/api/v1/penalties/${id}`), retry: false })
  const decide = useMutation({
    mutationFn: (action: 'approve' | 'cancel') => send('POST', `/api/v1/penalties/${id}/decision`, { action, note: note || null }),
    onSuccess: (_r, a) => {
      void qc.invalidateQueries({ queryKey: ['penalties'] })
      setNote('')
      toast.push({ title: a === 'approve' ? t('penalties.approved') : t('penalties.cancelled'), tone: 'success' })
    },
  })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const p = q.data
  if (!p) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  const det = p.details ?? {}

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <PageHeader title={p.label} subtitle={`${p.employee.full_name} · ${formatDate(p.incident_date, i18n.language)}`} backTo="/penalties" backLabel={t('penalties.title')} />
      <Card className="flex flex-col gap-3 p-6">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={TONE[p.status]}>{t(`penalties.status.${p.status}`)}</Badge>
          <Badge>{t(`letters.incidents.${p.incident_type}`)}</Badge>
          <Badge>{p.source === 'auto' ? t('penalties.auto') : t('penalties.manual')}</Badge>
          {p.step > 0 && <Badge>{t('penalties.stepN', { n: p.step })}</Badge>}
          {p.rule_version && <Badge>{t('penalties.ruleVersion', { v: p.rule_version })}</Badge>}
        </div>
        <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
          <Item label={t('penalties.amount')} value={p.amount > 0 ? money(p.amount) : t('penalties.noAmount')} />
          <Item label={t('penalties.block')} value={p.block_days > 0 ? t('penalties.blockDays', { count: p.block_days }) : '—'} />
          {typeof det.late_minutes === 'number' && <Item label={t('attendance.dash.lateLabel')} value={t('attendance.my.late', { m: det.late_minutes })} />}
          {typeof det.early_minutes === 'number' && <Item label={t('attendance.status.early')} value={t('attendance.my.early', { m: det.early_minutes })} />}
          <Item label={t('penalties.created')} value={formatDateTime(p.created_at, i18n.language)} />
          {p.decided_at && <Item label={t('answers.decidedAt')} value={formatDateTime(p.decided_at, i18n.language)} />}
        </dl>
        {p.reason && (
          <div className="rounded-control bg-surface-2 p-3 text-sm">
            <div className="text-xs text-muted">{t('attendance.record.reason')}</div>
            <p className="mt-1 whitespace-pre-wrap">{p.reason}</p>
          </div>
        )}
        {p.decision_note && (
          <div className="rounded-control bg-surface-2 p-3 text-sm">
            <div className="text-xs text-muted">{t('answers.decisionNote')}</div>
            <p className="mt-1 whitespace-pre-wrap">{p.decision_note}</p>
          </div>
        )}
        {p.block_applied && (
          <p role="status" className="text-sm text-danger">
            {p.unblocked_at ? t('penalties.unblocked', { date: formatDateTime(p.unblocked_at, i18n.language) }) : t('penalties.blockedUntil', { date: p.blocked_until ? formatDate(p.blocked_until, i18n.language) : '' })}
          </p>
        )}
        <div className="flex flex-wrap gap-2 pt-1">
          <Link to={`/employees/${p.employee.id}`}>
            <Button variant="outline">{t('employees.toCard')}</Button>
          </Link>
          {p.letters.map((l) => (
            <Link key={l.id} to={`/letters/${l.id}`}>
              <Button variant="outline">
                <FileWarning className="size-4" />
                {l.number} · {t(`letters.status.${l.status}`)}
              </Button>
            </Link>
          ))}
        </div>
      </Card>

      {(p.can_approve || p.can_cancel) && (
        <FormSection title={t('penalties.decision.title')} description={t('penalties.decision.hint')}>
          <Field label={t('answers.decision.note')}>
            {(fid) => <textarea id={fid} value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} rows={3} className="w-full rounded-control border border-border bg-surface px-3 py-2 text-sm" />}
          </Field>
          <div className="flex flex-wrap gap-3">
            {p.can_approve && (
              <Button disabled={decide.isPending} onClick={() => decide.mutate('approve')}>
                <Check className="size-4" />
                {t('penalties.decision.approve')}
              </Button>
            )}
            {p.can_cancel && (
              <Button variant="outline" className="text-danger" disabled={decide.isPending || !note.trim()} onClick={() => decide.mutate('cancel')}>
                <X className="size-4" />
                {t('penalties.decision.cancel')}
              </Button>
            )}
            {p.can_cancel && !note.trim() && <span className="self-center text-xs text-muted">{t('penalties.decision.cancelNeedsNote')}</span>}
          </div>
          {decide.isError && (
            <p role="alert" className="text-sm text-danger">
              {errorText(t, decide.error)}
            </p>
          )}
        </FormSection>
      )}
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
