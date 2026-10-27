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
import type { WhRow } from './api'

/** /warehouse/list: omborlar ro'yxati (yaratish/tahrirlash alohida sahifada). */
export function WarehousesPage() {
  const { t } = useTranslation()
  const manage = useCan()('warehouse.manage')
  const q = useQuery({ queryKey: ['warehouse', 'list'], queryFn: () => api<WhRow[]>('/api/v1/warehouse') })
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title={t('warehouse.list.title')}
        subtitle={t('warehouse.list.subtitle')}
        backTo="/warehouse"
        backLabel={t('warehouse.title')}
        actions={
          manage && (
            <Link to="/warehouse/new">
              <Button>
                <Plus className="size-4" />
                {t('warehouse.add')}
              </Button>
            </Link>
          )
        }
      />
      {!q.data ? (
        <Skeleton className="h-40" />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {q.data.map((w) => (
            <Link key={w.id} to={`/warehouse/${w.id}`}>
              <Card className="flex h-full flex-col gap-2 p-5 transition-shadow hover:shadow-card">
                <div className="flex items-start justify-between gap-2">
                  <h2 className="text-[15px] font-medium">{w.name}</h2>
                  {!w.is_active && <Badge>{t('needs.categories.inactive')}</Badge>}
                  {w.status?.gap && <Badge tone="danger">{t('warehouse.gap')}</Badge>}
                </div>
                <p className="text-sm text-muted">{w.shift ? `${w.shift.start} → ${w.shift.end} · ${w.shift.kind === 'flexible' ? t('warehouse.flexible') : t('warehouse.fixed')}${w.shift.min_work_minutes ? ` · min ${w.shift.min_work_minutes / 60} h` : ''}` : '—'}</p>
                <p className="mt-auto text-xs tabular-nums text-muted">
                  {t('warehouse.staffN', { count: w.status?.staff ?? 0 })} · {t('warehouse.minOnDuty')}: {w.min_on_duty}
                  {w.branch && ` · ${w.branch.name}`}
                </p>
              </Card>
            </Link>
          ))}
          {q.data.length === 0 && <p className="col-span-full py-10 text-center text-muted">{t('common.empty')}</p>}
        </div>
      )}
    </div>
  )
}
