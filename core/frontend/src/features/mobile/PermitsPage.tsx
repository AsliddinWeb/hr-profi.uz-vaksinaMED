import { useQuery } from '@tanstack/react-query'
import { UserPlus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { useCan } from '../auth/useAuth'
import { MobileTabs } from './MobileTabs'
import type { Permit } from './api'

/** /mobile/permits: kuzatuv ruxsati berilgan xodimlar. */
export function PermitsPage() {
  const { t, i18n } = useTranslation()
  const manage = useCan()('mobile.manage')
  const q = useQuery({ queryKey: ['mobile', 'permits'], queryFn: () => api<Permit[]>('/api/v1/mobile/permits') })
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <PageHeader
        title={t('mobile.title')}
        subtitle={t('mobile.subtitle')}
        actions={
          manage && (
            <Link to="/mobile/permits/new">
              <Button>
                <UserPlus className="size-4" />
                {t('mobile.permit.add')}
              </Button>
            </Link>
          )
        }
      />
      <MobileTabs />
      {!q.data ? (
        <Skeleton className="h-48" />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border text-xs text-muted">
                <tr>
                  <th className="px-5 py-2.5 font-medium">{t('payroll.line.employee')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('mobile.permit.window')}</th>
                  <th className="hidden px-5 py-2.5 font-medium sm:table-cell">{t('mobile.permit.interval')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('mobile.permit.state')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border tabular-nums">
                {q.data.map((p) => (
                  <tr key={p.employee.id}>
                    <td className="px-5 py-2.5">
                      {manage ? (
                        <Link to={`/mobile/permits/${p.employee.id}/edit`} className="font-medium hover:text-primary hover:underline">
                          {p.employee.name}
                        </Link>
                      ) : (
                        <span className="font-medium">{p.employee.name}</span>
                      )}
                      {!p.employee.has_account && <Badge tone="warning">{t('logistics.driver.noAccount')}</Badge>}
                    </td>
                    <td className="px-5 py-2.5 text-muted">
                      {p.window_start} – {p.window_end}
                    </td>
                    <td className="hidden px-5 py-2.5 text-muted sm:table-cell">{p.interval_s} s</td>
                    <td className="px-5 py-2.5">
                      {!p.enabled ? (
                        <Badge>{t('mobile.permit.disabled')}</Badge>
                      ) : p.consent_at ? (
                        <span className="flex flex-wrap items-center gap-1.5">
                          <Badge tone="success" title={formatDateTime(p.consent_at, i18n.language)}>
                            {t('mobile.permit.consented')}
                          </Badge>
                          {p.active_session_id && (
                            <Link to={`/mobile/sessions/${p.active_session_id}`}>
                              <Badge tone="warning">{t('mobile.my.live')}</Badge>
                            </Link>
                          )}
                        </span>
                      ) : (
                        <Badge tone="warning">{t('mobile.permit.awaiting')}</Badge>
                      )}
                    </td>
                  </tr>
                ))}
                {q.data.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-5 py-10 text-center text-muted">
                      {t('common.empty')}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}
