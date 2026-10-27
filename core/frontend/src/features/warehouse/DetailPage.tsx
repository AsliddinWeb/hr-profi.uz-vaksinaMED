import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ClipboardList, Pencil, UserMinus, UserPlus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { api, ApiError, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import { Kpi } from '../tasks/AnalyticsPage'
import type { WhRow, WhStatus } from './api'

/** /warehouse/:id: ombor kartasi, hozirgi holat va xodimlar tarkibi. */
export function DetailPage() {
  const { t } = useTranslation()
  const id = Number(useParams().id)
  const qc = useQueryClient()
  const confirm = useConfirm()
  const manage = useCan()('warehouse.manage')
  const w = useQuery({ queryKey: ['warehouse', 'one', id], queryFn: () => api<WhRow>(`/api/v1/warehouse/${id}`), retry: false })
  const st = useQuery({ queryKey: ['warehouse', 'status', id], queryFn: () => api<WhStatus>(`/api/v1/warehouse/${id}/status`), refetchInterval: 30_000 })
  const remove = useMutation({ mutationFn: (eid: number) => send('DELETE', `/api/v1/warehouse/${id}/staff/${eid}`), onSuccess: () => void qc.invalidateQueries({ queryKey: ['warehouse'] }) })
  if (w.error instanceof ApiError && w.error.status === 404) return <NotFound />
  if (!w.data || !st.data) return <Skeleton className="mx-auto h-96 max-w-4xl" />
  const wh = w.data
  const s = st.data
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title={wh.name}
        subtitle={wh.shift ? `${wh.shift.name}` : undefined}
        backTo="/warehouse"
        backLabel={t('warehouse.title')}
        actions={
          <>
            <Link to={`/warehouse/${id}/control`}>
              <Button variant="outline">
                <ClipboardList className="size-4" />
                {t('warehouse.controlReport')}
              </Button>
            </Link>
            {manage && (
              <Link to={`/warehouse/${id}/edit`}>
                <Button variant="outline">
                  <Pencil className="size-4" />
                  {t('common.edit')}
                </Button>
              </Link>
            )}
          </>
        }
      />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Kpi tint={s.gap ? 'rose' : 'mint'} label={t('warehouse.onDutyNow')} value={`${s.on_duty} / ${wh.min_on_duty}`} hint={s.gap ? t('warehouse.gap') : s.in_window ? t('warehouse.ok') : t('warehouse.outside')} />
        <Kpi label={t('warehouse.expectedToday')} value={String(s.expected)} />
        <Kpi tint="sand" label={t('warehouse.longOpenN')} value={String(s.long_open.length)} hint={`> ${wh.max_shift_hours} h`} />
        <Kpi label={t('warehouse.staff')} value={String(s.staff.length)} />
      </div>
      <Card className="p-6">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-[15px] font-medium">{t('warehouse.staff')}</h2>
          {manage && (
            <Link to={`/warehouse/${id}/staff/new`}>
              <Button variant="outline">
                <UserPlus className="size-4" />
                {t('warehouse.staffAdd')}
              </Button>
            </Link>
          )}
        </div>
        <ul className="mt-3 divide-y divide-border text-sm">
          {s.staff.map((p) => (
            <li key={p.employee.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
              <Link to={`/employees/${p.employee.id}`} className="font-medium hover:text-primary hover:underline">
                {p.employee.name}
              </Link>
              <span className="flex items-center gap-2">
                {p.on_duty && <Badge tone="success">{t('warehouse.onDuty')}</Badge>}
                {manage && (
                  <Button
                    variant="ghost"
                    className="h-8 px-2 text-danger"
                    aria-label={t('warehouse.staffRemove')}
                    disabled={remove.isPending}
                    onClick={async () => {
                      if (await confirm({ title: t('warehouse.staffRemove'), body: p.employee.name, danger: true, confirmLabel: t('warehouse.staffRemove') })) remove.mutate(p.employee.id)
                    }}
                  >
                    <UserMinus className="size-4" />
                  </Button>
                )}
              </span>
            </li>
          ))}
          {s.staff.length === 0 && <li className="py-6 text-center text-muted">{t('warehouse.noStaff')}</li>}
        </ul>
        {remove.isError && (
          <p role="alert" className="mt-2 text-sm text-danger">
            {errorText(t, remove.error)}
          </p>
        )}
      </Card>
    </div>
  )
}
