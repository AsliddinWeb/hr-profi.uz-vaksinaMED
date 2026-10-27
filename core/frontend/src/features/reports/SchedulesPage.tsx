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
import { ReportsTabs } from './ReportsTabs'
import { whenText, type Schedule } from './api'

/** /reports/schedules: jadvalli hisobotlar ro'yxati (yaratish va tahrirlash alohida sahifada). */
export function SchedulesPage() {
  const { t, i18n } = useTranslation()
  const q = useQuery({ queryKey: ['reports', 'schedules'], queryFn: () => api<Schedule[]>('/api/v1/reports/schedules') })
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader
        title={t('reports.title')}
        subtitle={t('reports.schedules.subtitle')}
        actions={
          <Link to="/reports/schedules/new">
            <Button>
              <Plus className="size-4" />
              {t('reports.schedules.add')}
            </Button>
          </Link>
        }
      />
      <ReportsTabs />
      {!q.data ? (
        <Skeleton className="h-48" />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border text-xs text-muted">
                <tr>
                  <th className="px-5 py-2.5 font-medium">{t('reports.schedules.name')}</th>
                  <th className="hidden px-5 py-2.5 font-medium md:table-cell">{t('reports.schedules.when')}</th>
                  <th className="hidden px-5 py-2.5 font-medium sm:table-cell">{t('reports.schedules.recipients')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('reports.schedules.next')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {q.data.map((s) => (
                  <tr key={s.id}>
                    <td className="px-5 py-2.5">
                      <Link to={`/reports/schedules/${s.id}/edit`} className="font-medium hover:text-primary hover:underline">
                        {s.name}
                      </Link>
                      <div className="text-xs text-muted">
                        {t(`reports.type.${s.report_type}`)} · {s.format.toUpperCase()} · {t(`reports.period.${s.period}`)}
                      </div>
                      {!s.is_active && <Badge className="mt-1">{t('reports.schedules.paused')}</Badge>}
                      {s.last_status === 'failed' && <Badge tone="danger" className="ml-1 mt-1">{t('reports.failed')}</Badge>}
                    </td>
                    <td className="hidden px-5 py-2.5 text-muted md:table-cell">{whenText(t, s)}</td>
                    <td className="hidden px-5 py-2.5 text-muted sm:table-cell">
                      {s.recipients.length} · {s.channels.map((c) => t(`reports.channel.${c}`)).join(', ')}
                    </td>
                    <td className="px-5 py-2.5 tabular-nums text-muted">{s.next_run_at ? formatDateTime(s.next_run_at, i18n.language) : '—'}</td>
                  </tr>
                ))}
                {q.data.length === 0 && (
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
