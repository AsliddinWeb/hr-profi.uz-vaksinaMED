import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, FileDown, FileText, PenLine, ScanLine, Undo2 } from 'lucide-react'
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
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { formatDate, formatDateTime } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { STATUS_TONE, type LetterDetail } from './api'

/** /letters/:id: xat tafsiloti, tarix, ko'rib chiqish (qabul/qaytarish), PDF va skaner. */
export function LetterDetailPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const [note, setNote] = useState('')
  const q = useQuery({ queryKey: ['letters', 'one', id], queryFn: () => api<LetterDetail>(`/api/v1/letters/${id}`), retry: false })
  const done = (msg: string) => {
    void qc.invalidateQueries({ queryKey: ['letters'] })
    toast.push({ title: msg, tone: 'success' })
  }
  const review = useMutation({
    mutationFn: (action: 'accept' | 'return') => send('POST', `/api/v1/letters/${id}/review`, { action, note: note || null }),
    onSuccess: (_r, a) => (setNote(''), done(a === 'accept' ? t('letters.review.accepted') : t('letters.review.returned'))),
  })
  const cancel = useMutation({ mutationFn: () => send('POST', `/api/v1/letters/${id}/cancel`), onSuccess: () => done(t('letters.cancelled')) })

  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const l = q.data
  if (!l) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  const err = review.isError ? errorText(t, review.error) : cancel.isError ? errorText(t, cancel.error) : null

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <PageHeader title={l.number} subtitle={l.employee.full_name} backTo="/letters" backLabel={t('letters.title')} />

      <Card className="flex flex-col gap-3 p-6">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={STATUS_TONE[l.status]}>{t(`letters.status.${l.status}`)}</Badge>
          {l.overdue && <Badge tone="danger">{t('letters.overdue')}</Badge>}
          <Badge>{t(`letters.incidents.${l.incident_type}`)}</Badge>
          {l.signed && <Badge tone="success">{t('letters.signed')}</Badge>}
        </div>
        <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
          <Item label={t('letters.form.incidentDate')} value={formatDate(l.incident_date, i18n.language)} />
          <Item label={t('letters.due')} value={l.due_date ? formatDate(l.due_date, i18n.language) : '—'} />
          <Item label={t('letters.requestedBy')} value={`${l.requested_by ?? '—'} · ${formatDateTime(l.requested_at, i18n.language)}`} />
          {l.submitted_at && <Item label={t('letters.submittedAt')} value={formatDateTime(l.submitted_at, i18n.language)} />}
        </dl>
        {l.incident_note && (
          <div className="rounded-control bg-surface-2 p-3 text-sm">
            <div className="text-xs text-muted">{t('letters.form.note')}</div>
            <p className="mt-1 whitespace-pre-wrap">{l.incident_note}</p>
          </div>
        )}
        {l.status === 'returned' && l.review_note && (
          <div role="status" className="rounded-control bg-danger/10 p-3 text-sm text-danger">
            <div className="text-xs">{t('letters.returnReason')}</div>
            <p className="mt-1 whitespace-pre-wrap">{l.review_note}</p>
          </div>
        )}
        <div className="flex flex-wrap gap-2 pt-1">
          {l.can_write && (
            <Link to={`/letters/${l.id}/write`}>
              <Button>
                <PenLine className="size-4" />
                {l.status === 'returned' ? t('letters.rewrite') : t('letters.write')}
              </Button>
            </Link>
          )}
          {l.signed && (
            <a href={`/api/v1/letters/${l.id}/pdf`} download>
              <Button variant="outline">
                <FileDown className="size-4" />
                PDF
              </Button>
            </a>
          )}
          {l.can_scan && (
            <Link to={`/letters/${l.id}/scan`}>
              <Button variant="outline">
                <ScanLine className="size-4" />
                {l.has_scan ? t('letters.replaceScan') : t('letters.uploadScan')}
              </Button>
            </Link>
          )}
          {l.has_scan && (
            <a href={`/api/v1/letters/${l.id}/scan`} target="_blank" rel="noreferrer">
              <Button variant="outline">
                <FileText className="size-4" />
                {t('letters.viewScan')}
              </Button>
            </a>
          )}
        </div>
      </Card>

      {l.snapshot && (
        <Card className="p-6">
          <h2 className="font-semibold">{t('letters.document')}</h2>
          <div className="mt-3 rounded-control border border-border p-5 text-sm">
            <p className="text-right text-muted">{l.snapshot.recipient}</p>
            <p className="mt-1 text-right text-muted">{l.snapshot.employee_name}</p>
            <h3 className="my-4 text-center font-semibold">{l.snapshot.title}</h3>
            <p className="whitespace-pre-wrap leading-relaxed">{l.snapshot.body}</p>
          </div>
          {l.signature && (
            <p className="mt-3 text-xs text-muted">
              {t('letters.signedBy', { name: l.signature.name, date: formatDateTime(l.signature.at, i18n.language) })} · SHA-256: <span className="font-mono">{l.content_hash?.slice(0, 16)}…</span>
            </p>
          )}
        </Card>
      )}

      {l.can_review && (
        <FormSection title={t('letters.review.title')} description={t('letters.review.hint')}>
          <Field label={t('letters.review.note')}>
            {(fid) => <textarea id={fid} value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} rows={3} className="w-full rounded-control border border-border bg-surface px-3 py-2 text-sm" />}
          </Field>
          <div className="flex flex-wrap gap-3">
            <Button disabled={review.isPending} onClick={() => review.mutate('accept')}>
              <Check className="size-4" />
              {t('letters.review.accept')}
            </Button>
            <Button variant="outline" className="text-danger" disabled={review.isPending || !note.trim()} onClick={() => review.mutate('return')}>
              <Undo2 className="size-4" />
              {t('letters.review.return')}
            </Button>
            {!note.trim() && <span className="self-center text-xs text-muted">{t('letters.review.returnNeedsNote')}</span>}
          </div>
        </FormSection>
      )}

      {l.can_cancel && (
        <div>
          <Button
            variant="outline"
            className="text-danger"
            disabled={cancel.isPending}
            onClick={async () => {
              if (await confirm({ title: t('letters.cancel'), body: t('letters.cancelConfirm'), danger: true, confirmLabel: t('letters.cancel') })) cancel.mutate()
            }}
          >
            {t('letters.cancel')}
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
          {l.events.map((e) => (
            <li key={e.id} className="relative">
              <span className="absolute -left-[26px] top-1.5 size-2.5 rounded-full bg-primary" aria-hidden />
              <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
                <span className="font-medium">{t(`letters.event.${e.action}`)}</span>
                <span className="text-xs text-muted">{formatDateTime(e.created_at, i18n.language)}</span>
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
