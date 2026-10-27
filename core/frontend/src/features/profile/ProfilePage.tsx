import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Monitor } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Field, Input } from '../../components/ui/Input'
import { api, send } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { errorText } from '../auth/errorText'
import { PasswordForm } from '../auth/PasswordForm'
import { useMe, type Me } from '../auth/useAuth'
import { TelegramCard } from './TelegramCard'

interface SessionRow {
  id: string
  ip: string | null
  user_agent: string | null
  last_used_at: string
  current: boolean
}

export function ProfilePage() {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const navigate = useNavigate()
  const { data: me } = useMe()
  const [name, setName] = useState(me?.full_name ?? '')
  const [phone, setPhone] = useState(me?.phone ?? '')

  const save = useMutation({
    mutationFn: () => send<Me>('PATCH', '/api/auth/me', { full_name: name, phone }),
    onSuccess: (m) => qc.setQueryData(['me'], m),
  })

  const sessions = useQuery({ queryKey: ['sessions'], queryFn: () => api<SessionRow[]>('/api/auth/sessions') })
  const revoke = useMutation({
    mutationFn: (id: string) => send('DELETE', `/api/auth/sessions/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sessions'] }),
  })
  const logoutAll = useMutation({
    mutationFn: () => send('POST', '/api/auth/logout-all'),
    onSuccess: async () => {
      qc.setQueryData(['me'], null)
      navigate('/login', { replace: true })
    },
  })

  if (!me) return null
  const roleName = i18n.language === 'ru' ? me.role.name_ru : me.role.name_uz

  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t('profile.title')}</h1>
        <p className="mt-1 text-sm text-muted">
          {me.login} · <Badge>{roleName}</Badge>
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-6">
          <h2 className="mb-4 font-semibold">{t('profile.data')}</h2>
          <form onSubmit={submit} className="flex flex-col gap-4">
            <Field label={t('users.fullName')}>
              {(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} minLength={2} />}
            </Field>
            <Field label={t('users.phone')}>
              {(id) => <Input id={id} value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" placeholder="+998 90 123 45 67" />}
            </Field>
            {save.isError && <p role="alert" className="text-sm text-danger">{errorText(t, save.error)}</p>}
            {save.isSuccess && <p className="text-sm text-success">{t('profile.saved')}</p>}
            <Button type="submit" disabled={save.isPending || name.trim().length < 2}>
              {t('common.save')}
            </Button>
          </form>
        </Card>

        <Card className="p-6">
          <h2 className="mb-4 font-semibold">{t('password.title')}</h2>
          <PasswordForm />
        </Card>
      </div>

      <TelegramCard />

      <Card className="p-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold">{t('profile.sessions')}</h2>
            <p className="text-sm text-muted">{t('profile.sessionsHint')}</p>
          </div>
          <Button variant="outline" onClick={() => logoutAll.mutate()} disabled={logoutAll.isPending}>
            {t('profile.logoutAll')}
          </Button>
        </div>
        <ul className="divide-y divide-border">
          {sessions.data?.map((s) => (
            <li key={s.id} className="flex items-center gap-3 py-3">
              <Monitor className="size-5 shrink-0 text-muted" />
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">{s.user_agent ?? '—'}</div>
                <div className="text-xs text-muted">
                  {s.ip ?? '—'} · {formatDateTime(s.last_used_at, i18n.language)}
                </div>
              </div>
              {s.current ? (
                <Badge tone="success">{t('profile.current')}</Badge>
              ) : (
                <Button variant="ghost" onClick={() => revoke.mutate(s.id)}>
                  {t('profile.revoke')}
                </Button>
              )}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}
