import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Banknote, CalendarCheck2, Store, Users } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'

import { BrandLogo } from '../../components/layout/BrandLogo'
import { TeamArt } from '../../components/illustrations'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Field, Input, PasswordInput } from '../../components/ui/Input'
import { send } from '../../lib/api'
import { setLang } from '../../lib/i18n'
import { useMeta } from '../meta/useMeta'
import { errorText } from './errorText'
import { useMe, type Me } from './useAuth'

export function LoginPage() {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const navigate = useNavigate()
  const location = useLocation()
  const { data: me } = useMe()
  const { data: meta } = useMeta()
  const [login, setLogin] = useState('')
  const [password, setPassword] = useState('')

  const from = (location.state as { from?: string } | null)?.from ?? '/'

  const mutation = useMutation({
    mutationFn: () => send<Me>('POST', '/api/auth/login', { login, password }),
    onSuccess: (user) => {
      qc.setQueryData(['me'], user)
      navigate(user.must_change_password ? '/change-password' : from, { replace: true })
    },
  })

  if (me) return <Navigate to={me.must_change_password ? '/change-password' : '/'} replace />

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (login.trim() && password) mutation.mutate()
  }

  const features = [
    { icon: Users, text: t('auth.feat1'), c: 'var(--c-blue)' },
    { icon: CalendarCheck2, text: t('auth.feat2'), c: 'var(--c-green)' },
    { icon: Banknote, text: t('auth.feat3'), c: 'var(--c-amber)' },
    { icon: Store, text: t('auth.feat4'), c: 'var(--c-rose)' },
  ]

  return (
    <div className="grid min-h-full lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <aside className="relative hidden overflow-hidden bg-[linear-gradient(145deg,#0b5ed7,#0a3f9c_70%,#082b6e)] p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div aria-hidden className="absolute -right-24 -top-24 size-96 rounded-full bg-white/10 blur-3xl" />
        <div aria-hidden className="absolute -bottom-32 -left-16 size-96 rounded-full bg-[#3ecf8e]/20 blur-3xl" />
        <img src="/logo-mark.png" alt="" className="relative h-12 w-auto self-start rounded-xl bg-white p-1.5" />
        <div className="relative">
          <TeamArt className="mx-auto w-full max-w-md" />
          <h2 className="mt-6 text-3xl font-semibold leading-tight tracking-tight">{t('auth.heroTitle')}</h2>
          <p className="mt-2 max-w-md text-[15px] text-white/75">{t('auth.heroText')}</p>
          <ul className="mt-6 grid max-w-md grid-cols-2 gap-3">
            {features.map(({ icon: Icon, text, c }) => (
              <li key={text} className="flex items-center gap-2.5 rounded-xl bg-white/10 px-3 py-2.5 text-[13px] backdrop-blur">
                <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-white" style={{ color: c }}>
                  <Icon className="size-4" />
                </span>
                {text}
              </li>
            ))}
          </ul>
        </div>
        <div className="relative text-xs text-white/60">© HR-Profi.uz</div>
      </aside>
      <div className="grid place-items-center bg-bg px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <BrandLogo src={meta?.brand.logo} alt={meta?.brand.name ?? 'HR-Profi'} className="mx-auto h-14 w-auto max-w-full lg:hidden" />
          <h1 className="sr-only">{meta?.brand.name ?? 'HR-Profi'}</h1>
          <p className="mt-1 text-sm text-muted lg:hidden">{meta?.brand.tagline}</p>
        </div>

        <Card className="rise p-7">
          <h2 className="text-base font-medium tracking-tight">{t('auth.title')}</h2>
          <p className="mb-5 mt-1 text-sm text-muted">{t('auth.subtitle')}</p>
          <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
            <Field label={t('auth.login')}>
              {(id) => (
                <Input
                  id={id}
                  value={login}
                  onChange={(e) => setLogin(e.target.value)}
                  autoComplete="username"
                  autoCapitalize="none"
                  autoFocus
                  placeholder={t('auth.loginPlaceholder')}
                />
              )}
            </Field>
            <Field label={t('auth.password')}>
              {(id) => (
                <PasswordInput
                  id={id}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  placeholder={t('auth.passwordPlaceholder')}
                />
              )}
            </Field>

            {mutation.isError && (
              <p role="alert" className="rounded-control bg-danger/10 px-3 py-2 text-sm text-danger">
                {errorText(t, mutation.error)}
              </p>
            )}

            <Button type="submit" disabled={mutation.isPending || !login.trim() || !password} className="h-10">
              {mutation.isPending ? t('app.loading') : t('auth.submit')}
            </Button>
          </form>
        </Card>

        <div className="mt-4 flex justify-center gap-2 text-xs font-semibold">
          {(['uz', 'ru'] as const).map((l) => (
            <button
              key={l}
              onClick={() => setLang(l)}
              className={i18n.language === l ? 'text-text' : 'text-muted transition-colors hover:text-text'}
            >
              {l.toUpperCase()}
            </button>
          ))}
        </div>
      </div>
      </div>
    </div>
  )
}
