import { useQuery } from '@tanstack/react-query'
import { Download } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Pagination } from '../../components/ui/Pagination'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDate, formatDateTime } from '../../lib/format'
import { useCan } from '../auth/useAuth'
import { ReportsTabs } from './ReportsTabs'
import { fileUrl, sizeKb, type RunPage } from './api'

const SIZE = 20

/** /reports/history: tuzilgan va menga yuborilgan hisobotlar (fayl 90 kun saqlanadi). */
export function HistoryPage() {
  const { t, i18n } = useTranslation()
  const manage = useCan()('reports.manage')
  const [scope, setScope] = useState<'mine' | 'all'>('mine')
  const [page, setPage] = useState(1)
  const q = useQuery({ queryKey: ['reports', 'runs', scope, page], queryFn: () => api<RunPage>(`/api/v1/reports/runs?scope=${scope}&page=${page}&size=${SIZE}`), placeholderData: (p) => p })
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader title={t('reports.title')} subtitle={t('reports.historyHint')} />
      <ReportsTabs />
      {manage && (
        <div className="flex rounded-control bg-(--seg-bg) p-0.5 text-[13px] self-start" role="group">
          {(['mine', 'all'] as const).map((s) => (
            <button key={s} onClick={() => (setScope(s), setPage(1))} aria-pressed={scope === s} className={scope === s ? 'rounded-lg bg-(--seg-on) px-3 py-1.5 font-medium text-text shadow-card' : 'rounded-lg px-3 py-1.5 text-muted transition-colors hover:text-text'}>
              {t(`reports.scope.${s}`)}
            </button>
          ))}
        </div>
      )}
      {!q.data ? (
        <Skeleton className="h-48" />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border text-xs text-muted">
                <tr>
                  <th className="px-5 py-2.5 font-medium">{t('reports.report')}</th>
                  <th className="hidden px-5 py-2.5 font-medium sm:table-cell">{t('reports.periodCol')}</th>
                  <th className="hidden px-5 py-2.5 font-medium md:table-cell">{t('reports.when')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('attendance.statusLabel')}</th>
                  <th className="px-5 py-2.5" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {q.data.items.map((r) => (
                  <tr key={r.id}>
                    <td className="px-5 py-2.5">
                      <div className="font-medium">{t(`reports.type.${r.type}`)}</div>
                      <div className="text-xs text-muted">
                        {r.format.toUpperCase()} · {r.schedule ? (r.schedule.name ?? t('reports.schedules.deleted')) : (r.created_by ?? '—')}
                      </div>
                    </td>
                    <td className="hidden px-5 py-2.5 tabular-nums text-muted sm:table-cell">{r.start ? `${formatDate(r.start, i18n.language)} – ${formatDate(r.end, i18n.language)}` : '—'}</td>
                    <td className="hidden px-5 py-2.5 tabular-nums text-muted md:table-cell">{formatDateTime(r.created_at, i18n.language)}</td>
                    <td className="px-5 py-2.5">{r.status === 'ok' ? <Badge tone="success">{sizeKb(r.size)}</Badge> : <Badge tone="danger">{t('reports.failed')}</Badge>}</td>
                    <td className="px-5 py-2.5 text-right">
                      {r.status === 'ok' && (
                        <a href={fileUrl(r.id)} download aria-label={t('reports.download')}>
                          <Button variant="outline" className="h-8">
                            <Download className="size-4" />
                          </Button>
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
                {q.data.items.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-5 py-10 text-center text-muted">
                      {t('common.empty')}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}
      {q.data && q.data.total > SIZE && <Pagination page={page} size={SIZE} total={q.data.total} onPage={setPage} />}
    </div>
  )
}
