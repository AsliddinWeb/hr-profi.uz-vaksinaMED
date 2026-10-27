import { useQuery } from '@tanstack/react-query'
import { PencilRuler } from 'lucide-react'
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
import { RulesView } from './RulesView'
import type { RulesOverview } from './api'

/** /penalties/rules: joriy qoidalar va versiyalar tarixi. */
export function RulesPage() {
  const { t, i18n } = useTranslation()
  const manage = useCan()('penalties.manage')
  const q = useQuery({ queryKey: ['penalties', 'rules'], queryFn: () => api<RulesOverview>('/api/v1/penalties/rules') })
  const d = q.data
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title={t('penalties.rules.title')}
        subtitle={t('penalties.rules.subtitle')}
        actions={
          manage && (
            <Link to="/penalties/rules/new">
              <Button>
                <PencilRuler className="size-4" />
                {t('penalties.rules.newVersion')}
              </Button>
            </Link>
          )
        }
      />
      {!d ? <Skeleton className="h-72" /> : d.current && <RulesView version={d.current} current />}
      {d && (
        <Card className="overflow-hidden">
          <h2 className="px-5 pt-5 font-semibold">{t('penalties.rules.history')}</h2>
          <ul className="mt-3 divide-y divide-border text-sm">
            {d.versions.map((v) => (
              <li key={v.id} className="flex flex-wrap items-center justify-between gap-2 px-5 py-2.5">
                <Link to={`/penalties/rules/${v.id}`} className="font-medium hover:text-primary hover:underline">
                  {t('penalties.ruleVersion', { v: v.version })}
                  {v.id === d.current?.id && <Badge className="ml-2" tone="success">{t('letters.currentBadge', { defaultValue: 'Joriy' })}</Badge>}
                </Link>
                <span className="text-muted">
                  {formatDateTime(v.created_at, i18n.language)} · {v.author ?? '—'} · {t('penalties.rules.used', { count: v.used ?? 0 })}
                </span>
                {v.note && <p className="w-full text-xs text-muted">{v.note}</p>}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}
