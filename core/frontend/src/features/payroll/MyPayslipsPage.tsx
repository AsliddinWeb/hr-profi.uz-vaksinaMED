import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api, ApiError } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { Payslip } from './Payslip'
import { RSTATUS_TONE, som, type LineDetail, type MyRow } from './api'

/** /payroll/my: mening ish haqi varaqalarim (faqat tasdiqlangan oylar). */
export function MyPayslipsPage() {
  const { t } = useTranslation()
  const q = useQuery({ queryKey: ['payroll', 'my'], queryFn: () => api<MyRow[]>('/api/v1/payroll/my') })
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <PageHeader title={t('payroll.my.title')} subtitle={t('payroll.my.subtitle')} />
      {!q.data ? (
        <Skeleton className="h-40" />
      ) : (
        <div className="flex flex-col gap-3">
          {q.data.map((r) => (
            <Link key={r.id} to={`/payroll/my/${r.id}`}>
              <Card className="flex items-center justify-between gap-3 p-5 transition-shadow hover:shadow-card">
                <div>
                  <div className="font-semibold">{r.period}</div>
                  <Badge tone={RSTATUS_TONE[r.status]}>{t(`payroll.status.${r.status}`)}</Badge>
                </div>
                <div className="text-right tabular-nums">
                  <div className="text-xs text-muted">{t('payroll.line.toPay')}</div>
                  <div className="text-lg font-semibold">{som(r.to_pay)}</div>
                </div>
              </Card>
            </Link>
          ))}
          {q.data.length === 0 && <p className="py-10 text-center text-muted">{t('payroll.my.empty')}</p>}
        </div>
      )}
    </div>
  )
}

/** /payroll/my/:id */
export function MyPayslipPage() {
  const { id } = useParams()
  const q = useQuery({ queryKey: ['payroll', 'my', id], queryFn: () => api<LineDetail>(`/api/v1/payroll/my/${id}`), retry: false })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!q.data) return <Skeleton className="mx-auto h-96 max-w-4xl" />
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader title={q.data.period} subtitle={q.data.employee.name ?? ''} backTo="/payroll/my" backLabel={'⟵'} />
      <Payslip l={q.data} />
    </div>
  )
}
