import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'

interface Row {
  employee: { id: number; name: string }
  branch: string | null
  score: number | null
  components: { key: string; value: number | null; weight: number; available: boolean }[]
}

/** /performance: xodimlarning yig'ma bahosi (online kuzatuv): davomat, o'qish, attestatsiya, intizom. Past ball birinchi. */
export function PerformancePage() {
  const { t } = useTranslation()
  const q = useQuery({ queryKey: ['growth', 'performance'], queryFn: () => api<{ weights: Record<string, number>; items: Row[] }>('/api/v1/growth/performance') })
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader title={t('growth.perf.title')} subtitle={t('growth.perf.subtitle')} />
      {!q.data ? (
        <Skeleton className="h-48" />
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs text-muted">
              <tr>
                <th className="px-4 py-2.5 font-medium">{t('attendance.employee')}</th>
                <th className="px-3 py-2.5 font-medium">{t('growth.perf.score')}</th>
                {['attendance', 'learning', 'attestation', 'discipline'].map((k) => (
                  <th key={k} className="px-3 py-2.5 font-medium">{t(`growth.settings.f.${k}`)} ({q.data.weights[k] ?? 0})</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {q.data.items.map((r) => (
                <tr key={r.employee.id}>
                  <td className="px-4 py-2.5">
                    <div className="font-medium">{r.employee.name}</div>
                    <div className="text-xs text-muted">{r.branch ?? '—'}</div>
                  </td>
                  <td className="px-3 py-2.5">
                    {r.score === null ? '—' : <Badge tone={r.score >= 80 ? 'success' : r.score >= 60 ? 'warning' : 'danger'}>{r.score}</Badge>}
                  </td>
                  {r.components.map((c) => (
                    <td key={c.key} className="px-3 py-2.5 tabular-nums text-muted">{c.available ? c.value : '—'}</td>
                  ))}
                </tr>
              ))}
              {q.data.items.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-muted">{t('common.empty')}</td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  )
}
