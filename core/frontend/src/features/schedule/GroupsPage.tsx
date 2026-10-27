import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { useCan } from '../auth/useAuth'
import type { WorkGroup } from './api'

export function GroupsPage() {
  const { t } = useTranslation()
  const manage = useCan()('schedule.manage')
  const list = useQuery({ queryKey: ['schedule', 'groups'], queryFn: () => api<WorkGroup[]>('/api/v1/schedule/groups') })

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader
        title={t('schedule.groups.title')}
        subtitle={t('schedule.groups.subtitle')}
        actions={
          manage && (
            <Link to="/schedule/groups/new">
              <Button>
                <Plus className="size-4" />
                {t('schedule.groups.add')}
              </Button>
            </Link>
          )
        }
      />
      {list.isLoading && <Skeleton className="h-40" />}
      <div className="grid gap-4 md:grid-cols-2">
        {list.data?.map((g) => (
          <Link key={g.id} to={`/schedule/groups/${g.id}/edit`} className="block">
            <Card className={`h-full p-5 transition-shadow hover:shadow-lg ${g.is_active ? '' : 'opacity-60'}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="truncate font-semibold">{g.name}</h3>
                  <div className="mt-0.5 text-xs text-muted">{t(`schedule.categories.${g.category}`)}</div>
                </div>
                <div className="flex shrink-0 flex-wrap justify-end gap-1.5">
                  {g.is_default && <Badge tone="success">{t('schedule.groups.default')}</Badge>}
                  {!g.is_active && <Badge>{t('schedule.inactive')}</Badge>}
                </div>
              </div>
              <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
                <dt className="text-muted">{t('schedule.groups.defaultShift')}</dt>
                <dd>{g.default_shift_name ?? '—'}</dd>
                <dt className="text-muted">{t('schedule.groups.weeklyOff')}</dt>
                <dd>{g.weekly_off_days.length ? g.weekly_off_days.map((d) => t(`schedule.wd.${d}`)).join(', ') : t('schedule.groups.noOff')}</dd>
                <dt className="text-muted">{t('schedule.groups.members')}</dt>
                <dd className="tabular-nums">{g.members}</dd>
              </dl>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {!g.observe_holidays && <Badge tone="warning">{t('schedule.groups.worksHolidays')}</Badge>}
                {!g.attendance_required && <Badge>{t('schedule.groups.noAttendance')}</Badge>}
              </div>
            </Card>
          </Link>
        ))}
      </div>
      {list.data?.length === 0 && <p className="py-10 text-center text-muted">{t('common.empty')}</p>}
    </div>
  )
}
