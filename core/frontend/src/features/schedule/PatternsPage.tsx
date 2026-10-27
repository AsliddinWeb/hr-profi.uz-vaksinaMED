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
import { CycleStrip } from './CycleStrip'
import type { Pattern, Shift } from './api'

export function PatternsPage() {
  const { t } = useTranslation()
  const manage = useCan()('schedule.manage')
  const list = useQuery({ queryKey: ['schedule', 'patterns'], queryFn: () => api<Pattern[]>('/api/v1/schedule/patterns') })
  const shifts = useQuery({ queryKey: ['schedule', 'shifts'], queryFn: () => api<Shift[]>('/api/v1/schedule/shifts') })
  const byId = new Map((shifts.data ?? []).map((s) => [s.id, s]))

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader
        title={t('schedule.patterns.title')}
        subtitle={t('schedule.patterns.subtitle')}
        actions={
          manage && (
            <Link to="/schedule/patterns/new">
              <Button>
                <Plus className="size-4" />
                {t('schedule.patterns.add')}
              </Button>
            </Link>
          )
        }
      />
      {list.isLoading && <Skeleton className="h-40" />}
      <div className="grid gap-4">
        {list.data?.map((p) => (
          <Link key={p.id} to={`/schedule/patterns/${p.id}/edit`}>
            <Card className={`p-5 transition-shadow hover:shadow-lg ${p.is_active ? '' : 'opacity-60'}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h3 className="font-semibold">{p.name}</h3>
                  {p.description && <p className="text-xs text-muted">{p.description}</p>}
                </div>
                <div className="flex gap-1.5">
                  <Badge>{t('schedule.patterns.cycleDays', { count: p.length })}</Badge>
                  <Badge tone="success">{t('schedule.patterns.workDays', { count: p.work_days })}</Badge>
                  {!p.is_active && <Badge>{t('schedule.inactive')}</Badge>}
                </div>
              </div>
              <div className="mt-4">
                <CycleStrip cycle={p.cycle} shifts={byId} />
              </div>
            </Card>
          </Link>
        ))}
      </div>
      {list.data?.length === 0 && <p className="py-10 text-center text-muted">{t('common.empty')}</p>}
    </div>
  )
}
