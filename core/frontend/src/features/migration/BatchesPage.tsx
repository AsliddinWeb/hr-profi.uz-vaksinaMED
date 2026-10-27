import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { Kpi } from '../tasks/AnalyticsPage'
import { MigrationTabs } from './MigrationTabs'
import { BATCH_TONE, type Batch } from './api'

/** /migration: import paketlari ro'yxati va solishtirish holati. */
export function BatchesPage() {
  const { t, i18n } = useTranslation()
  const list = useQuery({ queryKey: ['migration', 'batches'], queryFn: () => api<Batch[]>('/api/v1/migration/batches') })
  const sum = useQuery({ queryKey: ['migration', 'summary'], queryFn: () => api<{ applied_batches: number; checks: number; matched: number; mismatched: number }>('/api/v1/migration/summary') })
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader
        title={t('migration.title')}
        subtitle={t('migration.subtitle')}
        actions={
          <Link to="/migration/new">
            <Button>
              <Plus className="size-4" />
              {t('migration.newImport')}
            </Button>
          </Link>
        }
      />
      <MigrationTabs />
      {sum.data && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Kpi tint="lilac" label={t('migration.kpi.applied')} value={String(sum.data.applied_batches)} />
          <Kpi label={t('migration.kpi.checks')} value={String(sum.data.checks)} />
          <Kpi tint="mint" label={t('migration.kpi.matched')} value={String(sum.data.matched)} />
          <Kpi tint="rose" label={t('migration.kpi.mismatched')} value={String(sum.data.mismatched)} />
        </div>
      )}
      {!list.data ? (
        <Skeleton className="h-48" />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border text-xs text-muted">
                <tr>
                  <th className="px-5 py-2.5 font-medium">{t('migration.file')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('attendance.statusLabel')}</th>
                  <th className="hidden px-5 py-2.5 text-right font-medium sm:table-cell">{t('migration.result')}</th>
                  <th className="hidden px-5 py-2.5 font-medium md:table-cell">{t('reports.when')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {list.data.map((b) => (
                  <tr key={b.id}>
                    <td className="px-5 py-2.5">
                      <Link to={`/migration/batches/${b.id}`} className="font-medium hover:text-primary hover:underline">
                        {b.filename}
                      </Link>
                      <div className="text-xs text-muted">{t(`migration.dataset.${b.dataset}`)} · {t('migration.rows', { count: b.summary.rows ?? 0 })}</div>
                    </td>
                    <td className="px-5 py-2.5">
                      <Badge tone={BATCH_TONE[b.status]}>{t(`migration.status.${b.status}`)}</Badge>
                    </td>
                    <td className="hidden px-5 py-2.5 text-right tabular-nums text-muted sm:table-cell">
                      {b.summary.created !== undefined ? `+${b.summary.created} · ${t('migration.errors')}: ${b.summary.errors ?? 0}` : '—'}
                    </td>
                    <td className="hidden px-5 py-2.5 tabular-nums text-muted md:table-cell">{formatDateTime(b.created_at, i18n.language)}</td>
                  </tr>
                ))}
                {list.data.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-5 py-10 text-center text-muted">
                      {t('common.empty')}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}
