import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { Card } from '../../components/ui/Card'
import { PasswordForm } from './PasswordForm'
import { useMe } from './useAuth'

/** Vaqtinchalik parol bilan kirgan foydalanuvchi uchun majburiy sahifa. */
export function ChangePasswordPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { data: me } = useMe()
  return (
    <div className="grid min-h-full place-items-center px-4 py-10">
      <Card className="w-full max-w-sm p-6">
        <h1 className="text-lg font-semibold">{t('password.forcedTitle')}</h1>
        <p className="mb-5 mt-1 text-sm text-muted">
          {me?.must_change_password ? t('password.forcedText') : t('password.title')}
        </p>
        <PasswordForm onDone={() => navigate('/', { replace: true })} />
      </Card>
    </div>
  )
}
