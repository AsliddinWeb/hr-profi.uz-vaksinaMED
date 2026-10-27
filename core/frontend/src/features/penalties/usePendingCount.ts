import { useQuery } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { useCan } from '../auth/useAuth'

/** Tasdiq kutayotgan jarimalar soni (faqat tasdiqlovchilar uchun, yon panel belgisi). */
export function usePendingPenalties(): number {
  const enabled = useCan()('penalties.approve')
  const q = useQuery({ queryKey: ['penalties', 'summary'], queryFn: () => api<{ pending: number }>('/api/v1/penalties/summary'), enabled, refetchInterval: 60_000 })
  return enabled ? (q.data?.pending ?? 0) : 0
}
