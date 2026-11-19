import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Phone } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { api, send } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { errorText } from '../auth/errorText'
import { KIND_ICON, shortMoney, type MyActivity } from './api'
import { ActivityChip } from './parts'

const GROUPS = ['overdue', 'today', 'planned'] as const

/** /crm/activities: rejalashtirilgan faoliyatlar — kechikkan, bugungi, keyingi. Bir bosishda «Bajarildi». */
export function CrmActivitiesPage() {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const [scope, setScope] = useState<'mine' | 'all'>('mine')
  const list = useQuery({ queryKey: ['crm', 'activities', scope], queryFn: () => api<MyActivity[]>(`/api/v1/crm/activities?scope=${scope}`), refetchInterval: 30_000 })
  const done = useMutation({ mutationFn: (id: number) => send('POST', `/api/v1/crm/activities/${id}/done`, {}), onSuccess: () => void qc.invalidateQueries({ queryKey: ['crm'] }) })
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <PageHeader
        title={t('crm.activities.title')}
        subtitle={t('crm.activities.subtitle')}
        actions={
          <Select value={scope} onChange={(e) => setScope(e.target.value as 'mine' | 'all')} aria-label={t('crm.field.owner')} className="w-44">
            <option value="mine">{t('crm.filter.mine')}</option>
            <option value="all">{t('crm.filter.all')}</option>
          </Select>
        }
      />
      {done.isError && <p className="text-sm text-danger">{errorText(t, done.error)}</p>}
      {!list.data ? (
        <Skeleton className="h-64" />
      ) : list.data.length === 0 ? (
        <Card className="p-10 text-center text-sm text-muted">{t('crm.activities.empty')}</Card>
      ) : (
        GROUPS.map((g) => {
          const items = list.data.filter((a) => a.state === g)
          if (!items.length) return null
          return (
            <section key={g} className="flex flex-col gap-2">
              <h2 className={'px-1 text-sm font-semibold ' + (g === 'overdue' ? 'text-danger' : '')}>
                {t(`crm.activities.${g}`)} · {items.length}
              </h2>
              <Card className="divide-y divide-border">
                {items.map((a) => {
                  const Icon = KIND_ICON[a.kind]
                  return (
                    <div key={a.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                      <span className="grid size-9 shrink-0 place-items-center rounded-full bg-surface-2">
                        <Icon className="size-4" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-sm font-medium">{a.title}</span>
                          <ActivityChip a={a} />
                        </div>
                        <Link to={`/crm/deals/${a.deal.id}`} className="text-xs text-primary hover:underline">
                          {a.deal.title}
                          {a.deal.company ? ` · ${a.deal.company}` : ''} · {shortMoney(a.deal.amount, i18n.language)}
                        </Link>
                        <div className="text-[11px] text-muted">
                          {formatDate(a.due_date, i18n.language)}
                          {a.assignee ? ` · ${a.assignee}` : ''}
                        </div>
                      </div>
                      {a.deal.phone && (
                        <a href={`tel:${a.deal.phone}`} aria-label={a.deal.phone}>
                          <Button variant="outline" className="h-8 px-2.5">
                            <Phone className="size-4" />
                          </Button>
                        </a>
                      )}
                      <Button variant="success" className="h-8 px-3 text-xs" disabled={done.isPending} onClick={() => done.mutate(a.id)}>
                        <Check className="size-3.5" />
                        {t('crm.chatter.markDone')}
                      </Button>
                    </div>
                  )
                })}
              </Card>
            </section>
          )
        })
      )}
    </div>
  )
}
