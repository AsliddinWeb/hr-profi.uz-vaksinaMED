import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ExternalLink, Send } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { api, send } from '../../lib/api'
import { errorText } from '../auth/errorText'

interface Status {
  enabled: boolean
  bot_username: string | null
  linked: boolean
  telegram_username: string | null
  notify: boolean
}

interface LinkCode {
  url: string
  code: string
  expires_in: number
}

export function TelegramCard() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [link, setLink] = useState<LinkCode | null>(null)

  const status = useQuery({
    queryKey: ['telegram', 'status'],
    queryFn: () => api<Status>('/api/v1/telegram/status'),
    // Havola ochilgach ulanish yakunini kutamiz (realtime kelmasa zaxira sifatida)
    refetchInterval: (q) => (link && !q.state.data?.linked ? 3000 : false),
  })
  const refresh = () => qc.invalidateQueries({ queryKey: ['telegram'] })

  const getLink = useMutation({
    mutationFn: () => send<LinkCode>('POST', '/api/v1/telegram/link-code'),
    onSuccess: (l) => {
      setLink(l)
      window.open(l.url, '_blank', 'noopener')
    },
  })
  const toggle = useMutation({
    mutationFn: (notify: boolean) => send('PATCH', '/api/v1/telegram', { notify }),
    onSuccess: refresh,
  })
  const unlink = useMutation({
    mutationFn: () => send('DELETE', '/api/v1/telegram'),
    onSuccess: () => {
      setLink(null)
      return refresh()
    },
  })

  const s = status.data
  const error = getLink.error ?? toggle.error ?? unlink.error

  return (
    <Card className="p-6">
      <div className="mb-1 flex items-center gap-2">
        <Send className="size-4 text-info" />
        <h2 className="font-semibold">Telegram</h2>
        {s?.linked && <Badge tone="success">{t('telegram.linked')}</Badge>}
      </div>
      <p className="mb-4 text-sm text-muted">{t('telegram.hint')}</p>

      {s && !s.enabled && <p className="rounded-control bg-surface-2 px-3 py-2 text-sm text-muted">{t('telegram.disabled')}</p>}

      {s?.enabled && !s.linked && (
        <div className="flex flex-col gap-3">
          <Button onClick={() => getLink.mutate()} disabled={getLink.isPending} className="self-start">
            <ExternalLink className="size-4" />
            {t('telegram.connect')}
          </Button>
          {link && (
            <p className="text-sm text-muted">
              {t('telegram.waiting')}{' '}
              <a href={link.url} target="_blank" rel="noopener noreferrer" className="font-medium text-primary underline">
                {t('telegram.openAgain')}
              </a>
            </p>
          )}
        </div>
      )}

      {s?.enabled && s.linked && (
        <div className="flex flex-col gap-4">
          <p className="text-sm">
            {s.telegram_username ? `@${s.telegram_username}` : t('telegram.noUsername')}
          </p>
          <label className="flex cursor-pointer items-center gap-3 text-sm">
            <input
              type="checkbox"
              className="size-4 accent-[var(--primary)]"
              checked={s.notify}
              onChange={(e) => toggle.mutate(e.target.checked)}
            />
            {t('telegram.notify')}
          </label>
          <Button variant="outline" className="self-start" onClick={() => unlink.mutate()} disabled={unlink.isPending}>
            {t('telegram.unlink')}
          </Button>
        </div>
      )}

      {error && (
        <p role="alert" className="mt-3 text-sm text-danger">
          {errorText(t, error)}
        </p>
      )}
    </Card>
  )
}
