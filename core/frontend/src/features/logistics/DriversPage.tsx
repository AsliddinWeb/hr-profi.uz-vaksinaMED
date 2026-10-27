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
import { formatDate } from '../../lib/format'
import { useCan } from '../auth/useAuth'
import { LogisticsTabs } from './LogisticsTabs'
import { stageTone, type Driver } from './api'

/** /logistics/drivers: haydovchilar va guvohnoma muddatlari. */
export function DriversPage() {
  const { t, i18n } = useTranslation()
  const manage = useCan()('logistics.manage')
  const q = useQuery({ queryKey: ['logistics', 'drivers'], queryFn: () => api<Driver[]>('/api/v1/logistics/drivers') })
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <PageHeader
        title={t('logistics.title')}
        subtitle={t('logistics.subtitle')}
        actions={
          manage && (
            <Link to="/logistics/drivers/new">
              <Button>
                <UserPlus className="size-4" />
                {t('logistics.driver.add')}
              </Button>
            </Link>
          )
        }
      />
      <LogisticsTabs />
      {!q.data ? (
        <Skeleton className="h-48" />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border text-xs text-muted">
                <tr>
                  <th className="px-5 py-2.5 font-medium">{t('logistics.driver.name')}</th>
                  <th className="hidden px-5 py-2.5 font-medium sm:table-cell">{t('logistics.driver.license')}</th>
                  <th className="hidden px-5 py-2.5 font-medium md:table-cell">{t('logistics.driver.categories')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('logistics.driver.expires')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border tabular-nums">
                {q.data.map((d) => (
                  <tr key={d.employee.id}>
                    <td className="px-5 py-2.5">
                      {manage ? (
                        <Link to={`/logistics/drivers/${d.employee.id}/edit`} className="font-medium hover:text-primary hover:underline">
                          {d.employee.name}
                        </Link>
                      ) : (
                        <span className="font-medium">{d.employee.name}</span>
                      )}
                      <div className="text-xs text-muted">{d.employee.phone}</div>
                      {!d.employee.has_account && <Badge tone="warning">{t('logistics.driver.noAccount')}</Badge>}
                      {d.active_trip_id && (
                        <Link to={`/logistics/trips/${d.active_trip_id}`} className="ml-1">
                          <Badge tone="success">{t('logistics.vehicle.onTrip')}</Badge>
                        </Link>
                      )}
                    </td>
                    <td className="hidden px-5 py-2.5 text-muted sm:table-cell">{d.license_no ?? '—'}</td>
                    <td className="hidden px-5 py-2.5 text-muted md:table-cell">{d.categories ?? '—'}</td>
                    <td className="px-5 py-2.5">
                      {d.license_expires ? (
                        <>
                          {formatDate(d.license_expires, i18n.language)} <Badge tone={stageTone(d.license_stage)}>{(d.license_days_left ?? 0) < 0 ? t('logistics.doc.expired', { days: -(d.license_days_left ?? 0) }) : t('logistics.doc.daysLeft', { days: d.license_days_left })}</Badge>
                        </>
                      ) : (
                        '—'
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
