import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Megaphone, Pencil, UserPlus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api, ApiError, send } from '../../lib/api'
import { formatDate, formatDateTime } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import { STAGE_TONE, STAGES, salaryText, VSTATUS_TONE, type Board, type Vacancy, type VStatus } from './api'

/** /recruit/vacancies/:id: vakansiya, holat amallari va pipeline (ustunlar). */
export function VacancyDetailPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const qc = useQueryClient()
  const manage = useCan()('recruit.manage')
  const q = useQuery({ queryKey: ['recruit', 'vacancy', id], queryFn: () => api<Vacancy>(`/api/v1/recruit/vacancies/${id}`), retry: false })
  const board = useQuery({ queryKey: ['recruit', 'board', id], queryFn: () => api<Board>(`/api/v1/recruit/board?vacancy_id=${id}`), refetchInterval: 30_000 })
  const status = useMutation({ mutationFn: (s: VStatus) => send('POST', `/api/v1/recruit/vacancies/${id}/status`, { status: s }), onSuccess: () => void qc.invalidateQueries({ queryKey: ['recruit'] }) })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const v = q.data
  if (!v) return <Skeleton className="mx-auto h-96 max-w-6xl" />
  const next: VStatus[] = v.status === 'open' ? ['paused', 'closed'] : v.status === 'closed' ? ['open'] : ['open']

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <PageHeader
        title={v.title}
        subtitle={[v.branch?.name, v.position?.name].filter(Boolean).join(' · ')}
        backTo="/recruit/vacancies"
        backLabel={t('recruit.title')}
        actions={
          manage && (
            <>
              {v.status === 'open' && (
                <Link to={`/recruit/applications/new?vacancy_id=${v.id}`}>
                  <Button>
                    <UserPlus className="size-4" />
                    {t('recruit.application.add')}
                  </Button>
                </Link>
              )}
              <Link to={`/recruit/vacancies/${v.id}/promo`}>
                <Button variant="outline">
                  <Megaphone className="size-4" />
                  {t('recruitSources.promoBtn')}
                </Button>
              </Link>
              <Link to={`/recruit/vacancies/${v.id}/edit`}>
                <Button variant="outline">
                  <Pencil className="size-4" />
                  {t('common.edit')}
                </Button>
              </Link>
            </>
          )
        }
      />
      <Card className="flex flex-col gap-4 p-6">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={VSTATUS_TONE[v.status]}>{t(`recruit.vacancy.status.${v.status}`)}</Badge>
          {v.filled && <Badge tone="success">{t('recruit.vacancy.filled')}</Badge>}
          {manage && (
            <span className="ml-auto flex gap-2">
              {next.map((s) => (
                <Button key={s} variant="outline" disabled={status.isPending} onClick={() => status.mutate(s)}>
                  {t(`recruit.vacancy.setStatus.${s}`)}
                </Button>
              ))}
            </span>
          )}
        </div>
        {status.isError && (
          <p role="alert" className="text-sm text-danger">
            {errorText(t, status.error)}
          </p>
        )}
        <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-4">
          <Info label={t('recruit.vacancy.salary')}>{salaryText(v.salary_from, v.salary_to)}</Info>
          <Info label={t('recruit.vacancy.hired')}>
            {v.hired} / {v.openings}
          </Info>
          <Info label={t('recruit.vacancy.recruiter')}>{v.recruiter?.name ?? '—'}</Info>
          <Info label={t('recruit.vacancy.deadline')}>{v.deadline ? formatDate(v.deadline, i18n.language) : '—'}</Info>
        </dl>
        {v.description && <p className="whitespace-pre-wrap border-t border-border pt-4 text-sm leading-relaxed">{v.description}</p>}
        {v.requirements && (
          <div className="text-sm">
            <div className="mb-1 text-xs font-medium text-muted">{t('recruit.vacancy.requirements')}</div>
            <p className="whitespace-pre-wrap">{v.requirements}</p>
          </div>
        )}
      </Card>
      <h2 className="font-semibold">{t('recruit.vacancy.pipeline')}</h2>
      {!board.data ? (
        <Skeleton className="h-64" />
      ) : (
        <div className="grid gap-3 overflow-x-auto pb-2 sm:grid-cols-3 lg:grid-cols-6">
          {STAGES.map((s) => (
            <section key={s} className="flex min-w-44 flex-col gap-2 rounded-card bg-surface-2 p-3" aria-label={t(`recruit.stage.${s}`)}>
              <h3 className="flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-muted">
                {t(`recruit.stage.${s}`)}
                <Badge tone={STAGE_TONE[s]}>{board.data[s].total}</Badge>
              </h3>
              {board.data[s].items.map((a) => (
                <Link key={a.id} to={`/recruit/applications/${a.id}`} className="block rounded-control bg-surface p-3 text-sm shadow-card hover:ring-2 hover:ring-primary/30">
                  <div className="font-medium">{a.candidate.full_name}</div>
                  <div className="mt-0.5 text-xs text-muted">{a.interview_at && a.stage === 'interview' ? formatDateTime(a.interview_at, i18n.language) : a.candidate.phone}</div>
                  {a.rating && <div className="mt-1 text-xs text-warning">{'★'.repeat(a.rating)}</div>}
                </Link>
              ))}
              {board.data[s].items.length === 0 && <p className="py-2 text-center text-xs text-muted">—</p>}
            </section>
          ))}
        </div>
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
