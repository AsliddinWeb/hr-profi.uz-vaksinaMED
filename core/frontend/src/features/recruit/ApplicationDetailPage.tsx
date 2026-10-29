import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, UserCheck } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { api, ApiError, send } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { fromLocalInput, toLocalInput } from '../attendance/api'
import { errorText } from '../auth/errorText'
import { InvitationPanel, MatchCard } from './CoreParts'
import { PipelinePanel } from './PipelinePanel'
import { MOVABLE, REJECT_CODES, STAGES, type ApplicationDetail, type Stage } from './api'

const area = 'w-full rounded-control border border-border bg-surface px-3 py-2 text-sm'

/** /recruit/applications/:id: bosqichga o'tkazish, baho, rad etish, izoh va tarix. */
export function ApplicationDetailPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['recruit', 'application', id], queryFn: () => api<ApplicationDetail>(`/api/v1/recruit/applications/${id}`), retry: false })
  const [stage, setStage] = useState<string>('')
  const [when, setWhen] = useState('')
  const [rating, setRating] = useState('')
  const [note, setNote] = useState('')
  const [reason, setReason] = useState('')
  const [code, setCode] = useState('other')
  const [comment, setComment] = useState('')
  const done = () => {
    setNote('')
    setReason('')
    setComment('')
    setStage('')
    void qc.invalidateQueries({ queryKey: ['recruit'] })
  }
  const act = useMutation({ mutationFn: ({ path, body }: { path: string; body?: unknown }) => send('POST', `/api/v1/recruit/applications/${id}/${path}`, body), onSuccess: done })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const a = q.data
  if (!a) return <Skeleton className="mx-auto h-96 max-w-4xl" />
  const open = a.stage !== 'hired' && a.stage !== 'rejected'
  const target = (stage || a.stage) as Stage
  const needsWhen = target === 'interview'
  const cur = STAGES.indexOf(a.stage)

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader title={a.candidate.full_name ?? '—'} subtitle={a.vacancy.title ?? ''} backTo={`/recruit/vacancies/${a.vacancy.id}`} backLabel={a.vacancy.title ?? t('recruit.title')} actions={
        <Link to={`/recruit/candidates/${a.candidate.id}`}>
          <Button variant="outline">{t('recruit.application.candidateCard')}</Button>
        </Link>
      } />
      <Card className="p-5">
        <ol className="grid grid-cols-5 gap-2" aria-label={t('recruit.application.stage')}>
          {(['new', 'screening', 'interview', 'offer', 'hired'] as const).map((s, i) => {
            const reached = a.stage !== 'rejected' && i <= cur
            return (
              <li key={s} className="flex flex-col items-center gap-1.5 text-center" aria-current={s === a.stage ? 'step' : undefined}>
                <span className={'grid size-8 place-items-center rounded-full text-sm font-semibold ' + (reached ? 'bg-primary text-primary-fg' : 'bg-surface-2 text-muted')}>{reached ? <Check className="size-4" /> : i + 1}</span>
                <span className={'text-xs font-medium ' + (reached ? '' : 'text-muted')}>{t(`recruit.stage.${s}`)}</span>
              </li>
            )
          })}
        </ol>
        {a.stage === 'rejected' && <p className="mt-3 text-center text-sm text-danger">{t('recruit.application.rejectedHint', { reason: a.reject_reason ?? '' })}</p>}
        {a.stage === 'hired' && a.employee_id && (
          <p className="mt-3 text-center text-sm">
            <Link to={`/employees/${a.employee_id}`} className="font-medium text-primary hover:underline">
              {t('recruit.application.openEmployee')}
            </Link>
          </p>
        )}
      </Card>

      <Card className="grid gap-4 p-6 text-sm sm:grid-cols-4">
        <Info label={t('recruit.candidate.phone')}>{a.candidate.phone ?? '—'}</Info>
        <Info label={t('recruit.candidate.source')}>{a.candidate.source ? t(`recruit.source.${a.candidate.source}`) : '—'}</Info>
        <Info label={t('recruit.vacancy.recruiter')}>{a.recruiter?.name ?? '—'}</Info>
        <Info label={t('recruit.application.rating')}>{a.rating ? <span className="text-warning">{'★'.repeat(a.rating)}</span> : '—'}</Info>
        {a.interview_at && <Info label={t('recruit.application.interviewAt')}>{formatDateTime(a.interview_at, i18n.language)}</Info>}
        {a.candidate.skills.length > 0 && (
          <div className="flex flex-wrap gap-1.5 sm:col-span-4">
            {a.candidate.skills.map((s) => (
              <Badge key={s}>{s}</Badge>
            ))}
          </div>
        )}
      </Card>

      <PipelinePanel a={a} />

      <MatchCard a={a} />
      {a.can.manage && <InvitationPanel appId={a.id} open={open} />}
      {a.can.manage && open && (
        <Card className="flex flex-col gap-6 p-6">
          <section className="flex flex-col gap-3" aria-labelledby="app-stage">
            <h2 id="app-stage" className="font-semibold">{t('recruit.application.move')}</h2>
            <div className="grid gap-3 sm:grid-cols-3">
              <Select value={target} onChange={(e) => setStage(e.target.value)} aria-label={t('recruit.application.stage')}>
                {MOVABLE.map((s) => (
                  <option key={s} value={s}>
                    {t(`recruit.stage.${s}`)}
                  </option>
                ))}
              </Select>
              {needsWhen ? <Input type="datetime-local" value={when || toLocalInput(a.interview_at)} onChange={(e) => setWhen(e.target.value)} aria-label={t('recruit.application.interviewAt')} /> : <span />}
              <Select value={rating} onChange={(e) => setRating(e.target.value)} aria-label={t('recruit.application.rating')}>
                <option value="">{t('recruit.application.noRating')}</option>
                {[1, 2, 3, 4, 5].map((n) => (
                  <option key={n} value={n}>
                    {'★'.repeat(n)}
                  </option>
                ))}
              </Select>
            </div>
            <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={2000} placeholder={t('recruit.application.stageNote')} aria-label={t('recruit.application.stageNote')} className={area} />
            <div>
              <Button
                disabled={act.isPending || (target === a.stage && !rating && !when)}
                onClick={() => act.mutate({ path: 'stage', body: { stage: target, note: note || null, rating: rating ? Number(rating) : null, interview_at: needsWhen ? fromLocalInput(when || toLocalInput(a.interview_at)) : null } })}
              >
                {t('recruit.application.apply')}
              </Button>
            </div>
          </section>
          {a.can.hire && (
            <section className="flex flex-col gap-2 border-t border-border pt-5" aria-labelledby="app-hire">
              <h2 id="app-hire" className="font-semibold">{t('recruit.application.hire')}</h2>
              <p className="text-sm text-muted">{t('recruit.application.hireHint')}</p>
              <div>
                <Link to={`/recruit/applications/${a.id}/hire`}>
                  <Button>
                    <UserCheck className="size-4" />
                    {t('recruit.application.hireBtn')}
                  </Button>
                </Link>
              </div>
            </section>
          )}
          <section className="flex flex-col gap-2 border-t border-border pt-5" aria-labelledby="app-reject">
            <h2 id="app-reject" className="text-sm font-medium">{t('recruit.application.reject')}</h2>
            <Select value={code} onChange={(e) => setCode(e.target.value)} aria-label={t('recruitCore.reject.code')}>
              {REJECT_CODES.map((c) => (
                <option key={c} value={c}>
                  {t(`recruitCore.reject.codes.${c}`)}
                </option>
              ))}
            </Select>
            <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} maxLength={300} placeholder={t('recruit.application.rejectHint')} aria-label={t('recruit.application.reject')} className={area} />
            <div>
              <Button variant="outline" className="text-danger" disabled={reason.trim().length < 3 || act.isPending} onClick={() => act.mutate({ path: 'reject', body: { reason, code } })}>
                {t('recruit.application.rejectBtn')}
              </Button>
            </div>
          </section>
          {act.isError && (
            <p role="alert" className="text-sm text-danger">
              {errorText(t, act.error)}
            </p>
          )}
        </Card>
      )}
      {a.can.manage && a.stage === 'rejected' && (
        <Card className="flex items-center justify-between gap-3 p-5">
          <span className="text-sm text-muted">{t('recruit.application.reopenHint')}</span>
          <Button variant="outline" disabled={act.isPending} onClick={() => act.mutate({ path: 'reopen' })}>
            {t('recruit.application.reopen')}
          </Button>
        </Card>
      )}

      <Card className="flex flex-col gap-4 p-6">
        <h2 className="font-semibold">{t('recruit.application.history')}</h2>
        <ol className="flex flex-col gap-4 border-l border-border pl-5">
          {a.events.map((e) => (
            <li key={e.id} className="relative text-sm">
              <span className="absolute -left-[26px] top-1.5 size-2.5 rounded-full bg-primary" aria-hidden />
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="font-medium">
                  {e.action === 'stage' || e.action === 'rejected' ? t(`recruit.event.${e.action}`, { from: e.from ? t(`recruit.stage.${e.from}`) : '', to: e.to ? t(`recruit.stage.${e.to}`) : '' }) : e.action === 'rating' ? t('recruit.event.rating', { value: String(e.data?.to ?? '') }) : t(`recruit.event.${e.action}`)}
                </span>
                <span className="text-xs text-muted">{formatDateTime(e.created_at, i18n.language)}</span>
              </div>
              {e.actor && <div className="text-xs text-muted">{e.actor}</div>}
              {e.note && <p className="mt-1 whitespace-pre-wrap text-muted">{e.note}</p>}
            </li>
          ))}
        </ol>
        {a.can.manage && (
          <div className="flex gap-2">
            <Input value={comment} onChange={(e) => setComment(e.target.value)} maxLength={3000} placeholder={t('recruit.application.writeComment')} aria-label={t('recruit.application.writeComment')} />
            <Button variant="outline" disabled={!comment.trim() || act.isPending} onClick={() => act.mutate({ path: 'comments', body: { body: comment } })}>
              {t('tasks.send')}
            </Button>
          </div>
        )}
      </Card>
    </div>
  )
}

function Info({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="mt-1">{children}</dd>
    </div>
  )
}
