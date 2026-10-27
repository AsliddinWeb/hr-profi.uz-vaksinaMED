import { useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { useToast } from '../../components/ui/toastContext'
import { api } from '../../lib/api'
import { RealtimeClient } from '../../lib/realtime'
import { pick, type NotificationItem } from './api'

/** AppShell ichida bir marta: WebSocket ulaydi va hodisalarni cache/toast ga aylantiradi. */
export function useRealtime() {
  const qc = useQueryClient()
  const toast = useToast()
  const navigate = useNavigate()
  const { i18n } = useTranslation()

  useEffect(() => {
    const client = new RealtimeClient('/ws/notifications', async () => {
      // access token tugagan: api() refresh qiladi; hali ham 401 bo'lsa qayta ulanmaymiz
      try {
        await api('/api/auth/me')
        return true
      } catch {
        return false
      }
    })

    const off = client.subscribe((msg) => {
      if (msg.type === 'notification') {
        const n = msg.notification as NotificationItem
        void qc.invalidateQueries({ queryKey: ['notifications'] })
        void qc.invalidateQueries({ queryKey: ['unread'] })
        toast.push({
          title: pick(n.title, i18n.language) ?? '',
          body: pick(n.body, i18n.language),
          tone: n.severity,
          onClick: n.link ? () => navigate(n.link as string) : undefined,
        })
      } else if (msg.type === 'unread') {
        qc.setQueryData(['unread'], { count: msg.count as number })
        void qc.invalidateQueries({ queryKey: ['notifications'] })
      } else if (msg.type === 'telegram') {
        void qc.invalidateQueries({ queryKey: ['telegram'] })
      }
    })

    client.start()
    return () => {
      off()
      client.stop()
    }
    // til o'zgarganda qayta ulanish shart emas: toast matni push paytidagi tilda
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
}
