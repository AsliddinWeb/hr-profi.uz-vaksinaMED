import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { useCan } from '../auth/useAuth'
import { addDays, mondayOf, todayLocal } from '../attendance/api'
import { StarsView } from './Stars'
import { avgText, type Menu } from './api'

/** /canteen/menus: haftalik menyular (yaratish va tahrirlash alohida sahifada). */
export function MenusPage() {
  const { t, i18n } = useTranslation()
  const manage = useCan()('canteen.manage')
  const [start, setStart] = useState(mondayOf(todayLocal()))
  const end = addDays(start, 6)
  const q = useQuery({ queryKey: ['canteen', 'menus', start], queryFn: () => api<Menu[]>(`/api/v1/canteen/menus?start=${start}&end=${end}`) })
  const by = new Map((q.data ?? []).map((m) => [m.menu_date, m]))
  const days = Array.from({ length: 7 }, (_, i) => addDays(start, i))
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4">
      <PageHeader
        title={t('canteen.menus.title')}
        subtitle={t('canteen.menus.subtitle')}
        actions={
          manage && (
            <Link to="/canteen/menus/new">
              <Button>
                <Plus className="size-4" />
                {t('canteen.menus.add')}
              </Button>
            </Link>
          )
        }
      />
      <div className="flex items-center gap-2">
        <Button variant="outline" onClick={() => setStart(addDays(start, -7))} aria-label={t('common.prev', { defaultValue: '←' })}>
          <ChevronLeft className="size-4" />
        </Button>
        <span className="text-sm font-medium tabular-nums">
          {formatDate(start, i18n.language)} – {formatDate(end, i18n.language)}
        </span>
        <Button variant="outline" onClick={() => setStart(addDays(start, 7))} aria-label={t('common.next', { defaultValue: '→' })}>
          <ChevronRight className="size-4" />
        </Button>
        <Button variant="ghost" onClick={() => setStart(mondayOf(todayLocal()))}>
          {t('canteen.thisWeek')}
        </Button>
      </div>
      {!q.data ? (
        <Skeleton className="h-64" />
      ) : (
        <div className="flex flex-col gap-3">
          {days.map((d) => {
            const m = by.get(d)
            return (
              <Card key={d} className={'flex flex-wrap items-start justify-between gap-3 p-4 ' + (d === todayLocal() ? 'ring-2 ring-primary/30' : '')}>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-semibold">{formatDate(d, i18n.language)}</div>
                  {m ? (
                    <Link to={`/canteen/menus/${m.id}`} className="mt-1 block text-sm text-muted hover:text-primary hover:underline">
                      {m.dishes.map((x) => x.name).join(' · ')}
                    </Link>
                  ) : (
                    <p className="mt-1 text-sm text-muted">{t('canteen.menus.none')}</p>
                  )}
                </div>
                {m?.rating && m.rating.count > 0 ? (
                  <div className="text-right text-xs text-muted tabular-nums">
                    <StarsView value={m.rating.avg} />
                    <div>
                      {avgText(m.rating.avg)} · {m.rating.count}
                    </div>
                  </div>
                ) : (
                  manage &&
                  !m && (
                    <Link to={`/canteen/menus/new?date=${d}`}>
                      <Button variant="outline">{t('canteen.menus.addForDay')}</Button>
                    </Link>
                  )
                )}
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
