import { useQuery } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { useCan } from '../auth/useAuth'
import type { AiStatus } from './api'

export function useAiStatus() {
  const can = useCan()
  return useQuery({ queryKey: ['ai', 'status'], queryFn: () => api<AiStatus>('/api/v1/ai/status'), enabled: can('ai.use'), staleTime: 60_000, retry: false })
}
