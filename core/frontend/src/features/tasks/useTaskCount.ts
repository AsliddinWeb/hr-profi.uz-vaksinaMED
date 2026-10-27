import { useQuery } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { useCan } from '../auth/useAuth'

/** Menga biriktirilgan ochiq topshiriqlar (yon panel belgisi: muddati o'tganlar qizil bilan). */
export function useTaskCount(): { open: number; overdue: number } {
  const enabled = useCan()('tasks.own')
  const q = useQuery({ queryKey: ['tasks', 'summary'], queryFn: () => api<{ open: number; overdue: number }>('/api/v1/tasks/summary'), enabled, refetchInterval: 60_000 })
  return enabled && q.data ? q.data : { open: 0, overdue: 0 }
}
