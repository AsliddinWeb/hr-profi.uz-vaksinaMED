import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Upload } from 'lucide-react'
import { useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api, upload } from '../../lib/api'
import { errorText } from '../auth/errorText'
import { Kpi } from '../tasks/AnalyticsPage'
import { MigrationTabs } from './MigrationTabs'
import type { Reconcile } from './api'

/** /migration/reconcile: eski tizim nazorat summalari va yangi tizim raqamlari (jonli hisoblanadi). */
export function ReconcilePage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const input = useRef<HTMLInputElement>(null)
  const q = useQuery({ queryKey: ['migration', 'reconcile'], queryFn: () => api<Reconcile>('/api/v1/migration/reconcile'), refetchOnWindowFocus: true })
  const imp = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return upload<{ created: number }>('POST', '/api/v1/migration/checks/import', form)
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['migration'] }),
  })
  const d = q.data
  const fmt = (n: number) => n.toLocaleString(undefined, { maximumFractionDigits: 2 })
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader
        title={t('migration.title')}
        subtitle={t('migration.reconcileHint')}
        actions={
          <>
            <input ref={input} type="file" accept=".csv,.xlsx" className="sr-only" aria-label={t('migration.importChecks')} onChange={(e) => (e.target.files?.[0] && imp.mutate(e.target.files[0]), (e.target.value = ''))} />
            <Button variant="outline" disabled={imp.isPending} onClick={() => input.current?.click()}>
              <Upload className="size-4" />
              {t('migration.importChecks')}
            </Button>
            <Link to="/migration/checks/new">
              <Button>
                <Plus className="size-4" />
                {t('migration.addCheck')}
              </Button>
            </Link>
          </>
        }
      />
      <MigrationTabs />
      {imp.isError && <p role="alert" className="text-sm text-danger">{errorText(t, imp.error)}</p>}
      {!d ? (
        <Skeleton className="h-48" />
      ) : (
        <>
          <div className="grid grid-cols-3 gap-4">
            <Kpi label={t('migration.kpi.checks')} value={String(d.total)} />
            <Kpi tint="mint" label={t('migration.kpi.matched')} value={String(d.matched)} />
            <Kpi tint="rose" label={t('migration.kpi.mismatched')} value={String(d.mismatched)} />
          </div>
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-border text-xs text-muted">
                  <tr>
                    <th className="px-5 py-2.5 font-medium">{t('migration.check.label')}</th>
                    <th className="px-5 py-2.5 text-right font-medium">{t('migration.check.expected')}</th>
                    <th className="px-5 py-2.5 text-right font-medium">{t('migration.check.actual')}</th>
                    <th className="px-5 py-2.5 text-right font-medium">{t('migration.check.diff')}</th>
                    <th className="px-5 py-2.5 font-medium">{t('attendance.statusLabel')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border tabular-nums">
                  {d.items.map((x) => (
                    <tr key={x.id}>
                      <td className="px-5 py-2.5">
                        <Link to={`/migration/checks/${x.id}/edit`} className="font-medium hover:text-primary hover:underline">
                          {x.label}
                        </Link>
                        <div className="text-xs text-muted">
                          {t(`migration.metric.${x.metric}`)}
                          {x.period && ` · ${x.period}`}
                          {x.branch && ` · ${x.branch.name}`}
                        </div>
                      </td>
                      <td className="px-5 py-2.5 text-right">{fmt(x.expected)}</td>
                      <td className="px-5 py-2.5 text-right">{fmt(x.actual)}</td>
                      <td className={'px-5 py-2.5 text-right ' + (x.status === 'mismatch' ? 'font-semibold text-danger' : 'text-muted')}>{x.diff > 0 ? '+' : ''}{fmt(x.diff)}</td>
                      <td className="px-5 py-2.5">
                        <Badge tone={x.status === 'match' ? 'success' : 'danger'}>{t(`migration.check.${x.status}`)}</Badge>
                      </td>
                    </tr>
                  ))}
                  {d.items.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-5 py-10 text-center text-muted">
                        {t('migration.noChecks')}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  )
}
