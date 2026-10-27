import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { Skeleton } from '../../components/ui/Skeleton'
import { setLang } from '../../lib/i18n'
import { useMe } from './useAuth'

export function RequireAuth() {
  const { t } = useTranslation()
  const { data: me, isLoading } = useMe()
  const location = useLocation()

  // Foydalanuvchining saqlangan tilini qo'llaymiz
  useEffect(() => {
    if (me?.locale) setLang(me.locale)
  }, [me?.locale])

  if (isLoading) {
    return (
      <div className="grid min-h-full place-items-center p-8" role="status" aria-label={t('app.loading')}>
        <Skeleton className="h-10 w-48" />
      </div>
    )
  }
  if (!me) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (me.must_change_password && location.pathname !== '/change-password') {
    return <Navigate to="/change-password" replace />
  }
  return <Outlet />
}
