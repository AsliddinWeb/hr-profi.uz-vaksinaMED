import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Skeleton } from '../../components/ui/Skeleton'
import { api, ApiError } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { Payslip } from './Payslip'
import type { LineDetail } from './api'

/** /payroll/runs/:id/lines/:lid: xodimning hisob-kitob varaqasi (HR ko'rinishi). */
export function LinePage() {
  const { id, lid } = useParams()
  const q = useQuery({ queryKey: ['payroll', 'line', lid], queryFn: () => api<LineDetail>(`/api/v1/payroll/runs/${id}/lines/${lid}`), retry: false })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!q.data) return <Skeleton className="mx-auto h-96 max-w-4xl" />
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader title={q.data.employee.name ?? '—'} subtitle={[q.data.branch, q.data.department].filter(Boolean).join(' · ')} backTo={`/payroll/runs/${id}`} backLabel={q.data.period} />
      <Payslip l={q.data} />
    </div>
  )
}
