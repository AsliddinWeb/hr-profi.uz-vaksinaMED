import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Lock, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { api, ApiError, send } from '../../lib/api'
import { formatDate, formatDateTime } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { ESTATUS_TONE, type EnrollmentDetail } from './api'
import { DailyPanel } from './DailyPanel'
import { KIND_ICON } from './kindIcon'

const area = 'w-full rounded-control border border-border bg-surface px-3 py-2 text-sm'

/** /internship/enrollments/:id: stajyorning yo'li (bosqichlar), tasdiqlash, bekor qilish, tiklash. */
export function EnrollmentPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const qc = useQueryClient()
  const confirm = useConfirm()
  const [note, setNote] = useState('')
  const q = useQuery({ queryKey: ['internship', 'enrollment', id], queryFn: () => api<EnrollmentDetail>(`/api/v1/internship/enrollments/${id}`), retry: false, refetchInterval: 30_000 })
  const done = () => {
    setNote('')
    void qc.invalidateQueries({ queryKey: ['internship'] })
  }
  const act = useMutation({ mutationFn: ({ path, body }: { path: string; body?: unknown }) => send('POST', `/api/v1/internship/enrollments/${id}/${path}`, body ?? {}), onSuccess: done })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const e = q.data
  if (!e) return <Skeleton className="mx-auto h-96 max-w-4xl" />

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader title={e.employee.name ?? '—'} subtitle={e.program.name} backTo="/internship" backLabel={t('internship.title')} actions={<div className="flex gap-2"><Badge>{t(`onboarding.phases.${e.phase}`)}</Badge><Badge tone={ESTATUS_TONE[e.status]}>{t(`internship.status.${e.status}`)}</Badge></div>} />
      {e.phase === 'preboarding' && <DailyPanel enrollmentId={e.id} />}
      <Card className="flex flex-col gap-4 p-6">
        <div className="h-3 overflow-hidden rounded-full bg-surface-2" role="progressbar" aria-valuenow={e.progress.percent} aria-valuemin={0} aria-valuemax={100}>
          <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${e.progress.percent}%` }} />
        </div>
        <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-4">
          <Info label={t('internship.progress')}>
            {e.progress.done}/{e.progress.required} · {e.progress.percent}%
          </Info>
          <Info label={t('internship.avgScore')}>{e.progress.avg_score === null ? '—' : `${e.progress.avg_score}%`}</Info>
          <Info label={t('internship.enroll.mentor')}>{e.mentor?.name ?? '—'}</Info>
          <Info label={t('internship.enroll.due')}>
            <span className={e.overdue ? 'font-semibold text-danger' : ''}>{e.due_date ? formatDate(e.due_date, i18n.language) : '—'}</span>
          </Info>
        </dl>
        {e.status === 'ready' && <p className="rounded-control bg-warning/15 p-3 text-sm font-medium text-warning">{t('internship.readyHint')}</p>}
        {e.status === 'completed' && <p className="rounded-control bg-success/15 p-3 text-sm font-medium text-success">{t('internship.completedHint', { date: formatDateTime(e.completed_at, i18n.language) })}</p>}
        {e.note && <p className="whitespace-pre-wrap border-t border-border pt-3 text-sm text-muted">{e.note}</p>}
      </Card>

      <ol className="flex flex-col gap-3">
        {e.steps.map((s, i) => {
          const Icon = KIND_ICON[s.kind]
          return (
            <li key={s.id}>
              <Card className={'flex flex-wrap items-center gap-4 p-4 ' + (s.state === 'locked' ? 'opacity-60' : '')}>
                <span className={'grid size-10 shrink-0 place-items-center rounded-full ' + (s.state === 'done' ? 'bg-success/15 text-success' : 'bg-surface-2 text-muted')}>{s.state === 'done' ? <Check className="size-5" /> : s.state === 'locked' ? <Lock className="size-4" /> : <Icon className="size-5" />}</span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs tabular-nums text-muted">{i + 1}.</span>
                    <span className="font-medium">{s.title}</span>
                    <Badge>{t(`internship.kind.${s.kind}`)}</Badge>
                  </div>
                  <p className="mt-0.5 text-xs text-muted tabular-nums">
                    {s.score !== null && `${t('internship.score')}: ${s.score}%`}
                    {s.kind === 'test' && s.attempts > 0 && ` · ${t('internship.attempts', { count: s.attempts })}`}
                    {s.completed_at && ` · ${formatDateTime(s.completed_at, i18n.language)}`}
                  </p>
                </div>
                <span className="flex gap-2">
                  {e.can.learn && s.state !== 'locked' && (
                    <Link to={`/internship/enrollments/${e.id}/steps/${s.id}`}>
                      <Button variant={s.state === 'done' ? 'outline' : 'primary'}>{s.state === 'done' ? t('internship.review') : t('internship.start')}</Button>
                    </Link>
                  )}
                  {e.can.reset && (s.attempts > 0 || s.state === 'done') && (
                    <Button variant="outline" disabled={act.isPending} onClick={() => act.mutate({ path: `steps/${s.id}/reset` })} aria-label={t('internship.reset')} title={t('internship.reset')}>
                      <RotateCcw className="size-4" />
                    </Button>
                  )}
                </span>
              </Card>
            </li>
          )
        })}
      </ol>

      {(e.can.confirm || e.can.cancel) && (
        <Card className="flex flex-col gap-5 p-6">
          {e.can.confirm && (
            <section className="flex flex-col gap-3" aria-labelledby="int-confirm">
              <h2 id="int-confirm" className="font-semibold">{t('internship.confirm.title')}</h2>
              <p className="text-sm text-muted">{t('internship.confirm.hint')}</p>
              <textarea value={note} onChange={(ev) => setNote(ev.target.value)} rows={2} maxLength={2000} placeholder={t('recruit.application.stageNote')} aria-label={t('recruit.application.stageNote')} className={area} />
              <div>
                <Button disabled={act.isPending} onClick={() => act.mutate({ path: 'confirm', body: { note: note || null } })}>
                  <Check className="size-4" />
                  {t('internship.confirm.btn')}
                </Button>
              </div>
            </section>
          )}
          {e.can.cancel && (
            <section className={'flex flex-col gap-2 ' + (e.can.confirm ? 'border-t border-border pt-5' : '')} aria-labelledby="int-cancel">
              <h2 id="int-cancel" className="text-sm font-medium">{t('internship.cancel.title')}</h2>
              <div>
                <Button
                  variant="outline"
                  className="text-danger"
                  disabled={act.isPending}
                  onClick={async () => {
                    if (await confirm({ title: t('internship.cancel.title'), body: e.employee.name ?? '', danger: true, confirmLabel: t('internship.cancel.btn') })) act.mutate({ path: 'cancel' })
                  }}
                >
                  {t('internship.cancel.btn')}
                </Button>
              </div>
            </section>
          )}
          {act.isError && (
            <p role="alert" className="text-sm text-danger">
              {errorText(t, act.error)}
            </p>
          )}
        </Card>
      )}
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
