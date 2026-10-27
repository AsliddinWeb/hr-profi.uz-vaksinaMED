import { useQuery } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { useCan } from '../auth/useAuth'

/** Yon panel belgisi: menga kelgan ijrolar + tasdiq kutayotganlar + (dispetcher uchun) tayinlanmaganlar. */
export function useNeedCount(): number {
  const enabled = useCan()('needs.own')
  const q = useQuery({ queryKey: ['needs', 'summary'], queryFn: () => api<{ todo: number; to_confirm: number; unassigned: number }>('/api/v1/needs/summary'), enabled, refetchInterval: 60_000 })
  return enabled && q.data ? q.data.todo + q.data.to_confirm + q.data.unassigned : 0
}
