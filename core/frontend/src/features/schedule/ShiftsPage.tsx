import { useQuery } from '@tanstack/react-query'
import { Moon, Plus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { useCan } from '../auth/useAuth'
import { fmtDuration, shiftColor, shiftLabel, type Shift } from './api'

export function ShiftsPage() {
  const { t } = useTranslation()
  const manage = useCan()('schedule.manage')
  const list = useQuery({ queryKey: ['schedule', 'shifts'], queryFn: () => api<Shift[]>('/api/v1/schedule/shifts') })

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader
        title={t('schedule.shifts.title')}
        subtitle={t('schedule.shifts.subtitle')}
        actions={
          manage && (
            <Link to="/schedule/shifts/new">
              <Button>
                <Plus className="size-4" />
                {t('schedule.shifts.add')}
              </Button>
            </Link>
          )
        }
      />
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs text-muted">
              <tr>
                <th className="px-5 py-2.5 font-medium">{t('schedule.shifts.name')}</th>
                <th className="px-5 py-2.5 font-medium">{t('schedule.shifts.time')}</th>
                <th className="hidden px-5 py-2.5 font-medium md:table-cell">{t('schedule.shifts.work')}</th>
                <th className="hidden px-5 py-2.5 font-medium lg:table-cell">{t('schedule.shifts.rules')}</th>
                <th className="px-5 py-2.5" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {list.isLoading && (
                <tr>
                  <td colSpan={5} className="px-5 py-2.5">
                    <Skeleton className="h-24" />
                  </td>
                </tr>
              )}
              {list.data?.map((s) => (
                <tr key={s.id} className={s.is_active ? '' : 'opacity-60'}>
                  <td className="px-5 py-2.5">
                    <div className="flex items-center gap-3">
                      <span className="grid size-9 shrink-0 place-items-center rounded-control text-xs font-bold text-white" style={{ background: shiftColor(s) }}>
                        {shiftLabel(s)}
                      </span>
                      <div className="min-w-0">
                        <Link to={`/schedule/shifts/${s.id}/edit`} className="block truncate font-medium hover:text-primary hover:underline">
                          {s.name}
                        </Link>
                        <div className="text-xs text-muted">{t(`schedule.kind.${s.kind}`)}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-2.5 tabular-nums">
                    {s.start_time} – {s.end_time}
                    {s.overnight && (
                      <Badge className="ml-2" tone="neutral">
                        <Moon className="size-3" />
                        {s.start_time === s.end_time ? t('schedule.shifts.h24') : t('schedule.shifts.overnight')}
                      </Badge>
                    )}
                  </td>
                  <td className="hidden px-5 py-2.5 tabular-nums md:table-cell">
                    {t('schedule.hours', { h: fmtDuration(s.duration_minutes - s.break_minutes) })}
                    {s.break_minutes > 0 && <span className="text-muted"> · {t('schedule.shifts.breakShort', { m: s.break_minutes })}</span>}
                  </td>
                  <td className="hidden px-5 py-2.5 lg:table-cell">
                    {s.track_lateness ? <Badge tone="warning">{t('schedule.shifts.late', { m: s.late_grace_minutes })}</Badge> : <Badge>{t('schedule.shifts.noLate')}</Badge>}
                    {!s.is_active && <Badge className="ml-2">{t('schedule.inactive')}</Badge>}
                  </td>
                  <td className="px-5 py-2.5 text-right">
                    <Link to={`/schedule/shifts/${s.id}/edit`}>
                      <Button variant="ghost" className="h-8 px-2">
                        {manage ? t('common.edit') : t('common.view')}
                      </Button>
                    </Link>
                  </td>
                </tr>
              ))}
              {list.data?.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-5 py-10 text-center text-muted">
                    {t('common.empty')}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
