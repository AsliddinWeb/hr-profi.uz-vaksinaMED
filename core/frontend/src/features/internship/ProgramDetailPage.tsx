import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowDown, ArrowUp, Pencil, Plus, UserPlus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api, ApiError, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import type { ProgramDetail } from './api'
import { KIND_ICON } from './kindIcon'

/** /internship/programs/:id: dastur bosqichlari (tartibni o'zgartirish, qo'shish, tahrirlash). */
export function ProgramDetailPage() {
  const { t } = useTranslation()
  const id = Number(useParams().id)
  const qc = useQueryClient()
  const manage = useCan()('internship.manage')
  const q = useQuery({ queryKey: ['internship', 'program', id], queryFn: () => api<ProgramDetail>(`/api/v1/internship/programs/${id}`), retry: false })
  const order = useMutation({ mutationFn: (ids: number[]) => send('PUT', `/api/v1/internship/programs/${id}/order`, { ids }), onSuccess: () => void qc.invalidateQueries({ queryKey: ['internship'] }) })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const p = q.data
  if (!p) return <Skeleton className="mx-auto h-96 max-w-4xl" />
  const ids = p.steps_list.map((s) => s.id)
  const move = (i: number, d: number) => {
    const next = [...ids]
    ;[next[i], next[i + d]] = [next[i + d], next[i]]
    order.mutate(next)
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title={p.name}
        subtitle={p.description ?? undefined}
        backTo="/internship/programs"
        backLabel={t('internship.programs.title')}
        actions={
          manage && (
            <>
              <Link to={`/internship/enrollments/new?program_id=${p.id}`}>
                <Button>
                  <UserPlus className="size-4" />
                  {t('internship.enroll.add')}
                </Button>
              </Link>
              <Link to={`/internship/programs/${p.id}/edit`}>
                <Button variant="outline">
                  <Pencil className="size-4" />
                  {t('common.edit')}
                </Button>
              </Link>
            </>
          )
        }
      />
      <Card className="flex flex-wrap gap-x-8 gap-y-2 p-5 text-sm">
        <span>
          <span className="text-muted">{t('internship.programs.passScore')}: </span>
          {p.pass_score}%
        </span>
        <span>{p.sequential ? t('internship.programs.sequentialOn') : t('internship.programs.sequentialOff')}</span>
        <span>{t('internship.programs.enrolledN', { count: p.enrolled })}</span>
        {!p.is_active && <Badge>{t('needs.categories.inactive')}</Badge>}
      </Card>
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">{t('internship.programs.steps')}</h2>
        {manage && (
          <Link to={`/internship/programs/${p.id}/steps/new`}>
            <Button variant="outline">
              <Plus className="size-4" />
              {t('internship.step.add')}
            </Button>
          </Link>
        )}
      </div>
      {order.isError && (
        <p role="alert" className="text-sm text-danger">
          {errorText(t, order.error)}
        </p>
      )}
      <ol className="flex flex-col gap-3">
        {p.steps_list.map((s, i) => {
          const Icon = KIND_ICON[s.kind]
          return (
            <li key={s.id}>
              <Card className="flex items-center gap-4 p-4">
                <span className="grid size-10 shrink-0 place-items-center rounded-control bg-surface-2">
                  <Icon className="size-5 text-muted" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs tabular-nums text-muted">{i + 1}.</span>
                    <span className="font-medium">{s.title}</span>
                    <Badge>{t(`internship.kind.${s.kind}`)}</Badge>
                    {!s.required && <Badge>{t('checklists.optional')}</Badge>}
                  </div>
                  <p className="mt-0.5 text-xs text-muted">{s.kind === 'test' ? t('internship.step.questionsN', { count: s.question_count }) : s.file ? s.file.name : (s.url ?? '')}</p>
                </div>
                {manage && (
                  <span className="flex shrink-0 gap-1">
                    <Button variant="ghost" className="h-9 px-2" disabled={i === 0 || order.isPending} onClick={() => move(i, -1)} aria-label={t('checklists.templates.up')}>
                      <ArrowUp className="size-4" />
                    </Button>
                    <Button variant="ghost" className="h-9 px-2" disabled={i === ids.length - 1 || order.isPending} onClick={() => move(i, 1)} aria-label={t('checklists.templates.down')}>
                      <ArrowDown className="size-4" />
                    </Button>
                    <Link to={`/internship/steps/${s.id}/edit`}>
                      <Button variant="outline" className="h-9 px-3">
                        <Pencil className="size-4" />
                      </Button>
                    </Link>
                  </span>
                )}
              </Card>
            </li>
          )
        })}
        {p.steps_list.length === 0 && <li className="py-8 text-center text-muted">{t('common.empty')}</li>}
      </ol>
    </div>
  )
}
