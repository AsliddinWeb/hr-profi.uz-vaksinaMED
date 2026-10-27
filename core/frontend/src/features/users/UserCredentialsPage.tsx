import { Check, Copy } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, Navigate, useLocation } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'

interface CredentialsState {
  login: string
  name: string
  password: string
  reset?: boolean
  /** Natijadan keyin qaytish: masalan xodim kartasi */
  backTo?: string
  backLabel?: string
}

/** Foydalanuvchi yaratilgach / parol tiklangach: vaqtinchalik parol FAQAT shu yerda, bir marta ko'rsatiladi. */
export function UserCredentialsPage() {
  const { t } = useTranslation()
  const state = useLocation().state as CredentialsState | null
  const [copied, setCopied] = useState(false)

  // Sahifa yangilansa parol yo'qoladi: xavfsizlik uchun saqlanmaydi
  if (!state?.password) return <Navigate to="/users" replace />

  const text = `${t('auth.login')}: ${state.login}\n${t('auth.password')}: ${state.password}`

  return (
    <div className="mx-auto flex max-w-xl flex-col gap-6">
      <PageHeader
        title={state.reset ? t('users.passwordResetDone') : t('users.createdDone')}
        subtitle={state.name}
      />
      <Card className="p-6">
        <p className="text-sm text-muted">{t('users.credentialsHint')}</p>
        <pre className="mt-4 whitespace-pre-wrap rounded-control bg-surface-2 p-4 font-mono text-sm">{text}</pre>
        <Button
          variant="outline"
          className="mt-4"
          onClick={() => void navigator.clipboard?.writeText(text).then(() => setCopied(true))}
        >
          {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
          {copied ? t('common.copied') : t('common.copy')}
        </Button>
      </Card>
      <div className="flex flex-wrap gap-2">
        <Link to={state.backTo ?? '/users'}>
          <Button>{state.backLabel ?? t('users.backToList')}</Button>
        </Link>
        {!state.reset && !state.backTo && (
          <Link to="/users/new">
            <Button variant="outline">{t('users.addAnother')}</Button>
          </Link>
        )}
      </div>
    </div>
  )
}
