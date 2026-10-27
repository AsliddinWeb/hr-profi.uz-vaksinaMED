import { useQuery } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { useCan } from '../auth/useAuth'

/** Menga qaror kutayotgan so'rovlar soni (yon paneldagi belgi). */
export function useInboxCount(): number {
  const can = useCan()
  const enabled = can('answers.decide') || can('answers.manage')
  const q = useQuery({
    queryKey: ['answers', 'inbox-count'],
    queryFn: () => api<{ count: number }>('/api/v1/answers/inbox/count'),
    enabled,
    refetchInterval: 60_000,
  })
  return enabled ? (q.data?.count ?? 0) : 0
}
