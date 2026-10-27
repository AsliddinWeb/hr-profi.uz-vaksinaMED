import { useQuery } from '@tanstack/react-query'
import { CalendarPlus, Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { useCan } from '../auth/useAuth'
import { currentYear, pad, type Holiday } from './api'

export function HolidaysPage() {
  const { t } = useTranslation()
  const manage = useCan()('schedule.manage')
  const thisYear = currentYear()
  const [year, setYear] = useState(thisYear)
  const list = useQuery({ queryKey: ['schedule', 'holidays', year], queryFn: () => api<Holiday[]>(`/api/v1/schedule/holidays?year=${year}`) })

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title={t('schedule.holidays.title')}
        subtitle={t('schedule.holidays.subtitle')}
        actions={
          manage && (
            <>
              <Link to={`/schedule/holidays/seed?year=${year}`}>
                <Button variant="outline">
                  <CalendarPlus className="size-4" />
                  {t('schedule.holidays.seed')}
                </Button>
              </Link>
              <Link to={`/schedule/holidays/new?year=${year}`}>
                <Button>
                  <Plus className="size-4" />
                  {t('schedule.holidays.add')}
                </Button>
              </Link>
            </>
          )
        }
      />
      <Card className="flex items-center gap-3 p-4">
        <span className="text-sm text-muted">{t('schedule.holidays.year')}</span>
        <Select className="w-auto" value={year} onChange={(e) => setYear(Number(e.target.value))} aria-label={t('schedule.holidays.year')}>
          {[thisYear - 1, thisYear, thisYear + 1, thisYear + 2].map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </Select>
      </Card>
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs text-muted">
              <tr>
                <th className="px-5 py-2.5 font-medium">{t('schedule.holidays.date')}</th>
                <th className="px-5 py-2.5 font-medium">{t('schedule.holidays.name')}</th>
                <th className="hidden px-5 py-2.5 font-medium sm:table-cell">{t('schedule.holidays.kind')}</th>
                <th className="px-5 py-2.5" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {list.isLoading && (
                <tr>
                  <td colSpan={4} className="px-5 py-2.5">
                    <Skeleton className="h-24" />
                  </td>
                </tr>
              )}
              {list.data?.map((h) => (
                <tr key={h.id}>
                  <td className="px-5 py-2.5 tabular-nums">
                    {pad(h.day)}.{pad(h.month)}.{h.year ?? year}
                    {h.yearly && <Badge className="ml-2">{t('schedule.holidays.yearly')}</Badge>}
                  </td>
                  <td className="px-5 py-2.5">
                    <Link to={`/schedule/holidays/${h.id}/edit`} className="font-medium hover:text-primary hover:underline">
                      {h.name}
                    </Link>
                  </td>
                  <td className="hidden px-5 py-2.5 sm:table-cell">
                    <Badge tone={h.kind === 'holiday' ? 'danger' : 'success'}>{t(`schedule.holidays.kinds.${h.kind}`)}</Badge>
                  </td>
                  <td className="px-5 py-2.5 text-right">
                    <Link to={`/schedule/holidays/${h.id}/edit`}>
                      <Button variant="ghost" className="h-8 px-2">
                        {manage ? t('common.edit') : t('common.view')}
                      </Button>
                    </Link>
                  </td>
                </tr>
              ))}
              {list.data?.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-5 py-10 text-center text-muted">
                    {t('schedule.holidays.empty')}
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
