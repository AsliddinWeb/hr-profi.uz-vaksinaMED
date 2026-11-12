import { useQuery } from '@tanstack/react-query'

import { api } from '../../lib/api'

export interface Person {
  id: number
  full_name: string
  photo: boolean
  phone: string | null
  position: string | null
  branch: string | null
  department: string | null
  hire_date: string | null
  tenure_months: number | null
  status: string
  dismissal_date: string | null
  dismissal_reason: string | null
}
export interface Insights {
  scope: { department_id: number | null; name: string | null; departments: number }
  headcount: number
  positions_total: number
  branches_total?: number
  vacant_positions: number
  positions: { id: number; name: string; department: string | null; general: boolean; count: number; employees: Person[] }[]
  no_position: Person[]
  no_position_count: number
  newcomers: Person[]
  newcomers_count: number
  leavers: Person[]
  leavers_count: number
  analytics: {
    avg_tenure_months: number | null
    avg_age: number | null
    gender: Record<string, number>
    by_branch: { name: string; count: number }[]
    tenure_buckets: { lt3: number; m3_12: number; y1_3: number; gt3y: number }
    months: { month: string; hired: number; left: number }[]
    hired_12m: number
    left_12m: number
    turnover_pct: number
    leave_reasons: Record<string, number>
  }
  can_see_people: boolean
}

export const useInsights = (departmentId: number | null) =>
  useQuery({
    queryKey: ['org', 'insights', departmentId],
    queryFn: () => api<Insights>(`/api/v1/org/insights${departmentId ? `?department_id=${departmentId}` : ''}`),
  })

export function tenureText(t: (k: string, o?: Record<string, unknown>) => string, m: number | null) {
  if (m === null) return '—'
  const y = Math.floor(m / 12)
  return y ? t('orgx.tenureYM', { y, m: m % 12 }) : t('orgx.tenureM', { m })
}
