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
import { useCan } from '../auth/useAuth'
import { PayrollTabs } from './PayrollTabs'
import { RSTATUS_TONE, som, type RunRow } from './api'

/** /payroll: oylik hisob-kitoblar ro'yxati. */
export function RunsPage() {
  const { t } = useTranslation()
  const manage = useCan()('payroll.manage')
  const q = useQuery({ queryKey: ['payroll', 'runs'], queryFn: () => api<RunRow[]>('/api/v1/payroll/runs') })
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <PageHeader
        title={t('payroll.title')}
        subtitle={t('payroll.subtitle')}
        actions={
          manage && (
            <Link to="/payroll/runs/new">
              <Button>
                <Plus className="size-4" />
                {t('payroll.run.add')}
              </Button>
            </Link>
          )
        }
      />
      <PayrollTabs />
      {!q.data ? (
        <Skeleton className="h-48" />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border text-xs text-muted">
                <tr>
                  <th className="px-5 py-2.5 font-medium">{t('payroll.run.period')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('attendance.statusLabel')}</th>
                  <th className="px-5 py-2.5 text-right font-medium">{t('payroll.run.employees')}</th>
                  <th className="hidden px-5 py-2.5 text-right font-medium sm:table-cell">{t('payroll.line.gross')}</th>
                  <th className="px-5 py-2.5 text-right font-medium">{t('payroll.line.toPay')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border tabular-nums">
                {q.data.map((r) => (
                  <tr key={r.id}>
                    <td className="px-5 py-2.5 font-medium">
                      <Link to={`/payroll/runs/${r.id}`} className="hover:text-primary hover:underline">
                        {r.period}
                      </Link>
                    </td>
                    <td className="px-5 py-2.5">
                      <Badge tone={RSTATUS_TONE[r.status]}>{t(`payroll.status.${r.status}`)}</Badge>
                    </td>
                    <td className="px-5 py-2.5 text-right">{r.employees}</td>
                    <td className="hidden px-5 py-2.5 text-right text-muted sm:table-cell">{som(r.gross)}</td>
                    <td className="px-5 py-2.5 text-right font-medium">{som(r.to_pay)}</td>
                  </tr>
                ))}
                {q.data.length === 0 && (
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
    </div>
  )
}
