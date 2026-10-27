import { useQuery } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { useCan } from '../auth/useAuth'

/** Menga yozish kerak bo'lgan va ko'rib chiqishni kutayotgan xatlar soni (yon panel belgisi). */
export function useLettersCount(): number {
  const can = useCan()
  const enabled = can('letters.own') || can('letters.issue') || can('letters.review')
  const q = useQuery({ queryKey: ['letters', 'summary'], queryFn: () => api<{ to_write: number; to_review: number }>('/api/v1/letters/summary'), enabled, refetchInterval: 60_000 })
  return enabled ? (q.data ? q.data.to_write + q.data.to_review : 0) : 0
}
