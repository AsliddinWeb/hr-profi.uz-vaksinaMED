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
import type { LetterTemplate } from './api'

export function TemplatesPage() {
  const { t } = useTranslation()
  const list = useQuery({ queryKey: ['letters', 'templates'], queryFn: () => api<LetterTemplate[]>('/api/v1/letters/templates') })
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title={t('letters.templates.title')}
        subtitle={t('letters.templates.subtitle')}
        actions={
          <Link to="/letters/templates/new">
            <Button>
              <Plus className="size-4" />
              {t('letters.templates.add')}
            </Button>
          </Link>
        }
      />
      {list.isLoading && <Skeleton className="h-32" />}
      <div className="grid gap-4">
        {list.data?.map((x) => (
          <Link key={x.id} to={`/letters/templates/${x.id}/edit`}>
            <Card className={`p-5 transition-shadow hover:shadow-lg ${x.is_active ? '' : 'opacity-60'}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h3 className="font-semibold">{x.name}</h3>
                  <p className="text-xs text-muted">{x.title}</p>
                </div>
                <div className="flex gap-1.5">
                  {x.is_default && <Badge tone="success">{t('schedule.groups.default')}</Badge>}
                  {!x.is_active && <Badge>{t('schedule.inactive')}</Badge>}
                  <Badge>{t('letters.templates.used', { count: x.used })}</Badge>
                </div>
              </div>
              <p className="mt-3 line-clamp-2 whitespace-pre-wrap text-sm text-muted">{x.body_template}</p>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  )
}
