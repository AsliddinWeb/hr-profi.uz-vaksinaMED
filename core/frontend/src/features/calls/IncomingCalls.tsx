import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Phone, PhoneOff, Video } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useLocation, useNavigate } from 'react-router-dom'

import { Button } from '../../components/ui/Button'
import { api, send } from '../../lib/api'
import { useCan } from '../auth/useAuth'
import type { Incoming } from './api'

/** Kiruvchi qo'ng'iroq paneli: ekranning yuqori o'ng burchagida, har sahifada (3 soniyada tekshiriladi). */
export function IncomingCalls() {
  const { t } = useTranslation()
  const can = useCan()
  const qc = useQueryClient()
  const navigate = useNavigate()
  const here = useLocation().pathname
  const allowed = can('calls.own')
  const q = useQuery({ queryKey: ['calls', 'incoming'], queryFn: () => api<Incoming[]>('/api/v1/calls/incoming'), enabled: allowed, refetchInterval: 3000, retry: false })
  const decline = useMutation({ mutationFn: (id: number) => send('POST', `/api/v1/calls/${id}/decline`, {}), onSuccess: () => void qc.invalidateQueries({ queryKey: ['calls'] }) })
  const list = (q.data ?? []).filter((c) => here !== `/calls/${c.id}`)
  if (!allowed || list.length === 0) return null
  return (
    <div className="fixed right-4 top-4 z-50 flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2" role="alert" aria-live="assertive">
      {list.map((c) => (
        <div key={c.id} className="flex flex-col gap-3 rounded-card border border-border bg-surface p-4 shadow-card">
          <div className="flex items-center gap-3">
            <span className="grid size-10 animate-pulse place-items-center rounded-full bg-primary text-primary-fg">{c.media === 'video' ? <Video className="size-5" /> : <Phone className="size-5" />}</span>
            <div className="min-w-0">
              <div className="truncate font-semibold">{c.caller}</div>
              <div className="text-xs text-muted">{t(c.media === 'video' ? 'calls.incomingVideo' : 'calls.incomingAudio')}</div>
            </div>
          </div>
          <div className="flex gap-2">
            <Button className="flex-1" onClick={() => navigate(`/calls/${c.id}?join=1`)}>
              <Phone className="size-4" />
              {t('calls.accept')}
            </Button>
            <Button variant="outline" className="flex-1 text-danger" disabled={decline.isPending} onClick={() => decline.mutate(c.id)}>
              <PhoneOff className="size-4" />
              {t('calls.decline')}
            </Button>
          </div>
        </div>
      ))}
    </div>
  )
}
