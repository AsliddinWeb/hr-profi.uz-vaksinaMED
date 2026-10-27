import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { useCan } from './useAuth'

/** `perm` — bitta ruxsat; `any` — shulardan kamida bittasi. */
export function RequirePerm({ perm, any, children }: { perm?: string; any?: string[]; children: ReactNode }) {
  const can = useCan()
  const { t } = useTranslation()
  const allowed = any ? any.some(can) : perm ? can(perm) : true
  if (!allowed) {
    return (
      <div className="mx-auto mt-24 max-w-md text-center">
        <div className="text-5xl font-semibold text-muted">403</div>
        <h1 className="mt-4 text-xl font-semibold">{t('errors.forbidden')}</h1>
      </div>
    )
  }
  return <>{children}</>
}
