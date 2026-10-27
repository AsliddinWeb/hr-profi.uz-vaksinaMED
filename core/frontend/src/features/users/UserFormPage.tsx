import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { KeyRound, Power, UserX } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { useCan, useMe } from '../auth/useAuth'
import { roleName, type RoleOption, type UserRow } from './api'

/** /users/new va /users/:id/edit: bitta forma sahifasi. */
export function UserFormPage() {
  const { id } = useParams()
  const userId = id ? Number(id) : null
  const user = useQuery({
    queryKey: ['users', 'one', userId],
    queryFn: () => api<UserRow>(`/api/v1/users/${userId}`),
    enabled: userId !== null,
    retry: false,
  })

  if (userId === null) return <UserForm user={null} />
  if (user.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (user.error instanceof ApiError && user.error.status === 404) return <NotFound />
  if (!user.data) return null
  return <UserForm key={user.data.id} user={user.data} />
}

function UserForm({ user }: { user: UserRow | null }) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const can = useCan()
  const confirm = useConfirm()
  const { data: me } = useMe()
  const [fullName, setFullName] = useState(user?.full_name ?? '')
  const [phone, setPhone] = useState(user?.phone ?? '')
  const [roleKey, setRoleKey] = useState(user?.role_key ?? '')
  const [login, setLogin] = useState('')
  const [actionError, setActionError] = useState<string | null>(null)

  const roles = useQuery({ queryKey: ['assignable-roles'], queryFn: () => api<RoleOption[]>('/api/v1/users/assignable-roles') })

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ['users'] })
  }

  const save = useMutation({
    mutationFn: async () => {
      if (user) {
        await send('PATCH', `/api/v1/users/${user.id}`, { full_name: fullName, phone, role_key: roleKey })
        return null
      }
      return send<{ user: UserRow; temp_password: string | null }>('POST', '/api/v1/users', {
        full_name: fullName,
        phone: phone || null,
        role_key: roleKey,
        login: login || null,
      })
    },
    onSuccess: (res) => {
      refresh()
      if (res) {
        // Vaqtinchalik parol faqat bir marta: natija sahifasida ko'rsatiladi
        if (res.temp_password) {
          navigate('/users/credentials', { replace: true, state: { login: res.user.login, name: res.user.full_name, password: res.temp_password } })
        } else navigate('/users', { replace: true })
      } else {
        toast.push({ title: t('common.saved'), tone: 'success' })
        navigate('/users')
      }
    },
  })

  const onError = (e: unknown) => setActionError(errorText(t, e))
  const toggle = useMutation({
    mutationFn: (u: UserRow) => send('POST', `/api/v1/users/${u.id}/${u.is_active ? 'deactivate' : 'activate'}`),
    onSuccess: () => {
      refresh()
      navigate('/users')
    },
    onError,
  })
  const reset = useMutation({
    mutationFn: (u: UserRow) => send<{ temp_password: string }>('POST', `/api/v1/users/${u.id}/reset-password`),
    onSuccess: (r, u) => {
      refresh()
      navigate('/users/credentials', { replace: true, state: { login: u.login, name: u.full_name, password: r.temp_password, reset: true } })
    },
    onError,
  })
  const revoke = useMutation({
    mutationFn: (u: UserRow) => send('POST', `/api/v1/users/${u.id}/revoke-sessions`),
    onSuccess: () => toast.push({ title: t('users.sessionsRevoked'), tone: 'success' }),
    onError,
  })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  const lang = i18n.language
  const options = roles.data ?? []
  const isSelf = user?.id === me?.id

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader
        title={user ? t('users.edit') : t('users.add')}
        subtitle={user ? `${user.login}` : t('users.addHint')}
        backTo="/users"
        backLabel={t('users.title')}
      />

      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('users.sectionMain')}>
          <Field label={t('users.fullName')}>
            {(fid) => <Input id={fid} value={fullName} onChange={(e) => setFullName(e.target.value)} required minLength={2} maxLength={160} autoFocus />}
          </Field>
          <Field label={t('users.phone')}>
            {(fid) => <Input id={fid} value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" placeholder="+998 90 123 45 67" />}
          </Field>
        </FormSection>

        <FormSection title={t('users.sectionAccess')} description={t('users.sectionAccessHint')}>
          <Field label={t('users.role')}>
            {(fid) => (
              <Select id={fid} value={roleKey} onChange={(e) => setRoleKey(e.target.value)} required>
                <option value="" disabled>
                  {t('users.chooseRole')}
                </option>
                {options.map((r) => (
                  <option key={r.key} value={r.key} disabled={!r.assignable && r.key !== user?.role_key}>
                    {roleName(r, lang)}
                    {!r.assignable && r.key !== user?.role_key ? ` — ${t('users.noRight')}` : ''}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          {!user && (
            <Field label={t('users.login')} hint={t('users.loginHint')}>
              {(fid) => (
                <Input id={fid} value={login} onChange={(e) => setLogin(e.target.value.toLowerCase())} pattern="[a-z0-9._\-]{3,64}" autoCapitalize="none" />
              )}
            </Field>
          )}
          {!user && <p className="rounded-control bg-surface-2 px-3 py-2 text-sm text-muted">{t('users.tempPasswordNote')}</p>}
        </FormSection>

        <FormFooter error={save.isError ? errorText(t, save.error) : actionError}>
          <Button variant="outline" onClick={() => navigate('/users')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || fullName.trim().length < 2 || !roleKey}>
            {user ? t('common.save') : t('users.create')}
          </Button>
        </FormFooter>
      </form>

      {user && (can('users.reset_password') || can('users.deactivate') || can('sessions.manage')) && (
        <FormSection title={t('users.sectionSecurity')} description={t('users.sectionSecurityHint')} danger>
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
            {user.is_active ? <Badge tone="success">{t('users.active')}</Badge> : <Badge tone="danger">{t('users.blocked')}</Badge>}
            {user.must_change_password && <Badge tone="warning">{t('users.pending')}</Badge>}
            <span>
              {t('users.lastLogin')}: {formatDateTime(user.last_login_at, lang)}
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {can('users.reset_password') && (
              <Button
                variant="outline"
                disabled={reset.isPending}
                onClick={async () => {
                  if (await confirm({ title: t('users.resetPassword'), body: t('users.resetConfirm', { name: user.full_name }) })) reset.mutate(user)
                }}
              >
                <KeyRound className="size-4" />
                {t('users.resetPassword')}
              </Button>
            )}
            {can('sessions.manage') && (
              <Button
                variant="outline"
                disabled={revoke.isPending}
                onClick={async () => {
                  if (await confirm({ title: t('users.revokeSessions'), body: t('users.revokeConfirm') })) revoke.mutate(user)
                }}
              >
                {t('users.revokeSessions')}
              </Button>
            )}
            {can('users.deactivate') && !isSelf && (
              <Button
                variant="outline"
                className={user.is_active ? 'text-danger' : undefined}
                disabled={toggle.isPending}
                onClick={async () => {
                  const ok = await confirm({
                    title: user.is_active ? t('users.block') : t('users.unblock'),
                    body: user.is_active ? t('users.blockConfirm', { name: user.full_name }) : undefined,
                    danger: user.is_active,
                  })
                  if (ok) toggle.mutate(user)
                }}
              >
                {user.is_active ? <UserX className="size-4" /> : <Power className="size-4" />}
                {user.is_active ? t('users.block') : t('users.unblock')}
              </Button>
            )}
          </div>
        </FormSection>
      )}
    </div>
  )
}

