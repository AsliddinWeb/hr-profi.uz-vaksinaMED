import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'

import { api, send } from '../../lib/api'
import type { NotificationItem } from './api'

export function useUnread() {
  return useQuery({
    queryKey: ['unread'],
    queryFn: () => api<{ count: number }>('/api/v1/notifications/unread-count'),
    refetchInterval: 60_000, // WebSocket uzilgan bo'lsa zaxira
  })
}

export function useOpenNotification() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const read = useMutation({
    mutationFn: (id: number) => send('POST', `/api/v1/notifications/${id}/read`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['notifications'] })
      void qc.invalidateQueries({ queryKey: ['unread'] })
    },
  })
  return (n: NotificationItem) => {
    if (!n.read) read.mutate(n.id)
    if (n.link) navigate(n.link)
  }
}
