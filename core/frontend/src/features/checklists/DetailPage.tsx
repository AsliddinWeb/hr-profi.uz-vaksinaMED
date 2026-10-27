import { useQuery } from '@tanstack/react-query'
import { MapPin, Pencil } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api, ApiError } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { scoreText, scoreTone, type Answer, type VisitDetail } from './api'

/** /checklists/:id: yuborilgan tekshiruv natijasi (faqat o'qish). */
export function DetailPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const q = useQuery({ queryKey: ['checklists', 'one', id], queryFn: () => api<VisitDetail>(`/api/v1/checklists/visits/${id}`), retry: false })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const v = q.data
  if (!v) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  const sections = [...new Set(v.answers.map((a) => a.section ?? ''))]

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <PageHeader
        title={v.branch?.name ?? '—'}
        subtitle={`${v.template.name} · ${v.coordinator?.name ?? '—'}`}
        backTo="/checklists"
        backLabel={t('checklists.title')}
        actions={
          v.can.edit && (
            <Link to={`/checklists/${id}/fill`}>
              <Button>
                <Pencil className="size-4" />
                {t('checklists.continue')}
              </Button>
            </Link>
          )
        }
      />
      <Card tint={v.status === 'submitted' ? (scoreTone(v.score) === 'success' ? 'mint' : scoreTone(v.score) === 'danger' ? 'rose' : 'sand') : undefined} className="grid gap-4 p-6 sm:grid-cols-4">
        <div>
          <div className="text-xs text-muted">{t('checklists.score')}</div>
          <div className="mt-1 text-3xl font-semibold tabular-nums">{v.status === 'submitted' ? scoreText(v.score) : t('checklists.status.draft')}</div>
        </div>
        <div>
          <div className="text-xs text-muted">{t('checklists.critical')}</div>
          <div className={'mt-1 text-xl font-semibold tabular-nums ' + (v.critical_fails ? 'text-danger' : '')}>{v.critical_fails}</div>
        </div>
        <div>
          <div className="text-xs text-muted">{t('checklists.date')}</div>
          <div className="mt-1 text-sm tabular-nums">{formatDateTime(v.submitted_at ?? v.started_at, i18n.language)}</div>
        </div>
        <div>
          <div className="text-xs text-muted">GPS</div>
          <div className="mt-1 flex items-center gap-1 text-sm">
            <MapPin className={'size-4 ' + (v.geo_ok ? 'text-success' : 'text-warning')} />
            {v.distance_m === null ? t('checklists.noGps') : `${v.distance_m} m`}
          </div>
        </div>
        {v.geo_reason && (
          <p className="text-sm sm:col-span-4">
            <span className="text-muted">{t('checklists.reason')}: </span>
            {v.geo_reason}
          </p>
        )}
      </Card>
      {sections.map((sec) => (
        <Card key={sec} className="divide-y divide-border p-0">
          {sec && <h2 className="px-5 py-2.5 text-sm font-semibold">{sec}</h2>}
          {v.answers.filter((a) => (a.section ?? '') === sec).map((a) => (
            <div key={a.id} className="flex flex-col gap-1.5 px-5 py-2.5 text-sm">
              <div className="flex items-start justify-between gap-3">
                <span>
                  {a.text}
                  {a.critical && <Badge tone="danger" className="ml-2">{t('checklists.critical')}</Badge>}
                </span>
                <AnswerBadge a={a} />
              </div>
              {a.comment && <p className="text-muted">{a.comment}</p>}
              <div className="flex flex-wrap gap-2">
                {v.files.filter((f) => f.item_id === a.id).map((f) => (
                  <a key={f.id} href={`/api/v1/checklists/visits/${v.id}/files/${f.id}`} target="_blank" rel="noreferrer" className="rounded-full bg-surface-2 px-2.5 py-1 text-xs hover:underline">
                    {f.filename}
                  </a>
                ))}
              </div>
            </div>
          ))}
        </Card>
      ))}
      {v.note && (
        <Card className="p-5 text-sm">
          <div className="mb-1 text-xs font-medium text-muted">{t('checklists.note')}</div>
          <p className="whitespace-pre-wrap">{v.note}</p>
        </Card>
      )}
    </div>
  )
}

function AnswerBadge({ a }: { a: Answer }) {
  const { t } = useTranslation()
  if (a.na) return <Badge>{t('checklists.na')}</Badge>
  if (a.value === null) return <Badge>—</Badge>
  if (a.kind === 'yesno') return <Badge tone={a.value ? 'success' : 'danger'}>{t(a.value ? 'checklists.yes' : 'checklists.no')}</Badge>
  return <Badge tone={a.value >= 4 ? 'success' : a.value >= 2 ? 'warning' : 'danger'}>{a.value}/5</Badge>
}
