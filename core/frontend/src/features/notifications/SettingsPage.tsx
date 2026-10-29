import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Lock } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { PageHeader } from '../../components/layout/PageHeader'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api, send } from '../../lib/api'
import { errorText } from '../auth/errorText'
import { catLabel, type PrefsResponse } from './api'

/** /notifications/settings: qaysi toifadagi xabarlarni olishni foydalanuvchi o'zi tanlaydi (majburiylari o'chmaydi). */
export function NotificationSettingsPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['notifications', 'prefs'], queryFn: () => api<PrefsResponse>('/api/v1/notifications/preferences') })
  const save = useMutation({
    mutationFn: (muted: string[]) => send('PUT', '/api/v1/notifications/preferences', { muted }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['notifications'] }),
  })
  const muted = (q.data?.categories ?? []).filter((c) => c.muted).map((c) => c.key)
  const toggle = (key: string, on: boolean) => save.mutate(on ? muted.filter((k) => k !== key) : [...muted, key])
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-5">
      <PageHeader title={t('notifications.settingsTitle')} subtitle={t('notifications.settingsHint')} backTo="/notifications" backLabel={t('notifications.title')} />
      {!q.data ? (
        <Skeleton className="h-64" />
      ) : (
        <Card className="divide-y divide-border p-2">
          {q.data.categories.map((c) => (
            <label key={c.key} className="flex items-center justify-between gap-3 px-3 py-3 text-sm">
              <span className="flex items-center gap-2">
                {catLabel(t, c.key)}
                {c.mandatory && (
                  <span className="inline-flex items-center gap-1 text-xs text-muted">
                    <Lock className="size-3" />
                    {t('notifications.mandatory')}
                  </span>
                )}
              </span>
              <input type="checkbox" className="size-5" checked={c.mandatory || !c.muted} disabled={c.mandatory || save.isPending} onChange={(e) => toggle(c.key, e.target.checked)} aria-label={catLabel(t, c.key)} />
            </label>
          ))}
        </Card>
      )}
      {save.isError && (
        <p role="alert" className="text-sm text-danger">
          {errorText(t, save.error)}
        </p>
      )}
    </div>
  )
}
