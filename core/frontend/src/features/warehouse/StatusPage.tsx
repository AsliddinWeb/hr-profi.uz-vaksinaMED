import { useQuery } from '@tanstack/react-query'
import { AlertTriangle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { useCan } from '../auth/useAuth'
import { hm, type WhStatus } from './api'

/** /warehouse: omborlar holati: kim ishda, minimumga yetdimi, yetishmovchilik (30 soniyada yangilanadi). */
export function StatusPage() {
  const { t } = useTranslation()
  const manage = useCan()('warehouse.manage')
  const q = useQuery({ queryKey: ['warehouse', 'status'], queryFn: () => api<WhStatus[]>('/api/v1/warehouse/status'), refetchInterval: 30_000 })
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader
        title={t('warehouse.title')}
        subtitle={t('warehouse.subtitle')}
        actions={
          manage && (
            <Link to="/warehouse/list">
              <Button variant="outline">{t('warehouse.manage')}</Button>
            </Link>
          )
        }
      />
      {!q.data ? (
        <Skeleton className="h-64" />
      ) : q.data.length === 0 ? (
        <Card className="p-10 text-center text-muted">
          {t('warehouse.none')}
          {manage && (
            <div className="mt-3">
              <Link to="/warehouse/new">
                <Button>{t('warehouse.add')}</Button>
              </Link>
            </div>
          )}
        </Card>
      ) : (
        q.data.map((s) => <Panel key={s.warehouse.id} s={s} />)
      )}
    </div>
  )
}

function Panel({ s }: { s: WhStatus }) {
  const { t, i18n } = useTranslation()
  const w = s.warehouse
  return (
    <Card tint={s.gap ? 'rose' : undefined} className="flex flex-col gap-4 p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to={`/warehouse/${w.id}`} className="text-lg font-semibold hover:text-primary hover:underline">
            {w.name}
          </Link>
          <p className="text-xs text-muted">
            {s.window ? `${s.window.shift} · ${formatDateTime(s.window.start, i18n.language)} → ${formatDateTime(s.window.end, i18n.language)}` : t('warehouse.noShift')}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {s.gap && (
            <Badge tone="danger">
              <AlertTriangle className="size-3" />
              {t('warehouse.gap')}
            </Badge>
          )}
          {!s.in_window && !s.no_shift && <Badge>{t('warehouse.outside')}</Badge>}
          <span className="text-2xl font-semibold tabular-nums">
            {s.on_duty}
            <span className="text-base font-normal text-muted"> / {w.min_on_duty}</span>
          </span>
        </div>
      </div>
      {s.long_open.length > 0 && (
        <p role="alert" className="rounded-control bg-warning/15 p-2.5 text-sm text-warning">
          {s.long_open.map((x) => t('warehouse.longOpen', { name: x.name, hours: x.hours })).join('; ')}
        </p>
      )}
      <ul className="grid gap-2 sm:grid-cols-2">
        {s.staff.map((p) => (
          <li key={p.employee.id} className="flex items-center justify-between gap-3 rounded-control bg-surface px-3 py-2 text-sm shadow-card">
            <span className="min-w-0">
              <span className="block truncate font-medium">{p.employee.name}</span>
              <span className="text-xs text-muted tabular-nums">
                {p.check_in_at ? formatDateTime(p.check_in_at, i18n.language).slice(-5) : '—'}
                {p.check_out_at ? ` → ${formatDateTime(p.check_out_at, i18n.language).slice(-5)}` : ''}
                {p.worked_minutes > 0 && ` · ${hm(p.worked_minutes)}`}
              </span>
            </span>
            {p.on_duty ? (
              <Badge tone={p.met_min ? 'success' : 'warning'}>{p.met_min || p.remaining_minutes === null ? t('warehouse.onDuty') : t('warehouse.remaining', { time: hm(p.remaining_minutes ?? 0) })}</Badge>
            ) : p.check_out_at ? (
              <Badge tone={p.met_min === false ? 'warning' : 'neutral'}>{p.met_min === false ? t('warehouse.belowMin') : t('warehouse.done')}</Badge>
            ) : (
              <Badge>{p.scheduled ? t('warehouse.notYet') : t('warehouse.off')}</Badge>
            )}
          </li>
        ))}
        {s.staff.length === 0 && <li className="text-sm text-muted">{t('warehouse.noStaff')}</li>}
      </ul>
    </Card>
  )
}
