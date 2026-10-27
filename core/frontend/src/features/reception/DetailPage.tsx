import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { LogIn, LogOut, Pencil } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Info } from '../../components/ui/Info'
import { Input } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { api, ApiError, send } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { STATUS_TONE, type VisitDetail } from './api'

/** /reception/:id: mehmon kartasi va amallar (keldi / ketdi / bekor qilish) sahifa ichida. */
export function DetailPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const qc = useQueryClient()
  const confirm = useConfirm()
  const [badge, setBadge] = useState('')
  const q = useQuery({ queryKey: ['reception', 'one', id], queryFn: () => api<VisitDetail>(`/api/v1/reception/${id}`), retry: false, refetchInterval: 20_000 })
  const act = useMutation({ mutationFn: ({ path, body }: { path: string; body?: unknown }) => send('POST', `/api/v1/reception/${id}/${path}`, body ?? {}), onSuccess: () => void qc.invalidateQueries({ queryKey: ['reception'] }) })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const v = q.data
  if (!v) return <Skeleton className="mx-auto h-72 max-w-3xl" />
  const showActions = v.can.arrive || v.can.leave || v.can.cancel

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <PageHeader
        title={v.visitor_name}
        subtitle={`${t(`reception.purpose.${v.purpose}`)}${v.company ? ` · ${v.company}` : ''}`}
        backTo="/reception"
        backLabel={t('reception.title')}
        actions={
          v.can.edit && (
            <Link to={`/reception/${id}/edit`}>
              <Button variant="outline">
                <Pencil className="size-4" />
                {t('common.edit')}
              </Button>
            </Link>
          )
        }
      />
      <Card className="flex flex-col gap-4 p-6">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={STATUS_TONE[v.status]}>{t(`reception.status.${v.status}`)}</Badge>
          {v.badge_no && <Badge>#{v.badge_no}</Badge>}
        </div>
        <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
          <Info label={t('reception.host')}>{v.host?.name ?? '—'}</Info>
          <Info label={t('reception.branch')}>{v.branch?.name ?? '—'}</Info>
          <Info label={t('reception.phone')}>{v.visitor_phone ?? '—'}</Info>
          <Info label={t('reception.expectedAt')}>{v.expected_at ? formatDateTime(v.expected_at, i18n.language) : '—'}</Info>
          <Info label={t('reception.arrivedAt')}>{v.arrived_at ? formatDateTime(v.arrived_at, i18n.language) : '—'}</Info>
          <Info label={t('reception.leftAt')}>{v.left_at ? formatDateTime(v.left_at, i18n.language) : '—'}</Info>
          <Info label={t('reception.doc')}>{v.doc_info ?? '—'}</Info>
          <Info label={t('reception.plate')}>{v.vehicle_plate ?? '—'}</Info>
          <Info label={t('reception.registeredBy')}>{v.registered_by ?? '—'}</Info>
          {v.checked_in_by && <Info label={t('reception.checkedInBy')}>{v.checked_in_by}</Info>}
          {v.checked_out_by && <Info label={t('reception.checkedOutBy')}>{v.checked_out_by}</Info>}
        </dl>
        {v.note && <p className="whitespace-pre-wrap border-t border-border pt-4 text-sm">{v.note}</p>}
      </Card>
      {showActions && (
        <Card className="flex flex-col gap-4 p-6">
          {v.can.arrive && (
            <section className="flex flex-wrap items-end gap-3">
              <div>
                <label htmlFor="badge" className="mb-1 block text-xs text-muted">
                  {t('reception.badge')}
                </label>
                <Input id="badge" value={badge} onChange={(e) => setBadge(e.target.value)} maxLength={20} className="w-36" />
              </div>
              <Button disabled={act.isPending} onClick={() => act.mutate({ path: 'arrive', body: { badge_no: badge || null } })}>
                <LogIn className="size-4" />
                {t('reception.arrive')}
              </Button>
            </section>
          )}
          {v.can.leave && (
            <section>
              <Button disabled={act.isPending} onClick={() => act.mutate({ path: 'leave' })}>
                <LogOut className="size-4" />
                {t('reception.leave')}
              </Button>
            </section>
          )}
          {v.can.cancel && (
            <section className="border-t border-border pt-4 first:border-0 first:pt-0">
              <Button
                variant="outline"
                className="text-danger"
                disabled={act.isPending}
                onClick={async () => {
                  if (await confirm({ title: t('reception.cancelTitle'), body: v.visitor_name, danger: true, confirmLabel: t('reception.cancelBtn') })) act.mutate({ path: 'cancel' })
                }}
              >
                {t('reception.cancelBtn')}
              </Button>
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
