import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { Avatar } from './Avatar'
import type { Employee } from './api'

interface Group {
  reasons: string[]
  members: (Employee & { documents: number })[]
}

/** /employees/duplicates: ehtimoliy dublikat guruhlari. */
export function DuplicatesPage() {
  const { t, i18n } = useTranslation()
  const groups = useQuery({ queryKey: ['employees', 'duplicates'], queryFn: () => api<Group[]>('/api/v1/employees/duplicates') })

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader title={t('employees.duplicatesTitle')} subtitle={t('employees.duplicatesSubtitle')} backTo="/employees" backLabel={t('employees.title')} />
      {groups.isLoading && <Skeleton className="h-40" />}
      {groups.data?.length === 0 && <Card className="p-10 text-center text-muted">{t('employees.noDuplicates')}</Card>}
      {groups.data?.map((g) => (
        <Card key={g.members.map((m) => m.id).join('-')} className="p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-2">
              {g.reasons.map((r) => (
                <Badge key={r} tone="warning">
                  {t(`employees.reason.${r}`)}
                </Badge>
              ))}
            </div>
            <Link to={`/employees/merge?ids=${g.members.map((m) => m.id).join(',')}`}>
              <Button>{t('employees.merge')}</Button>
            </Link>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {g.members.map((m) => (
              <div key={m.id} className="rounded-control border border-border p-4">
                <div className="flex items-center gap-3">
                  <Avatar id={m.id} name={m.full_name} hasPhoto={m.has_photo} size={40} />
                  <div className="min-w-0">
                    <Link to={`/employees/${m.id}`} className="block truncate font-medium hover:text-primary hover:underline">
                      {m.full_name}
                    </Link>
                    <div className="text-xs text-muted">№{m.employee_no}</div>
                  </div>
                  <Badge tone={m.status === 'active' ? 'success' : 'danger'} className="ml-auto">
                    {t(`employees.status_${m.status}`)}
                  </Badge>
                </div>
                <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                  <dt className="text-muted">{t('employees.phone')}</dt>
                  <dd>{m.phone ?? '—'}</dd>
                  <dt className="text-muted">{t('employees.position')}</dt>
                  <dd>{m.position?.name ?? '—'}</dd>
                  <dt className="text-muted">{t('employees.hireDate')}</dt>
                  <dd>{formatDate(m.hire_date, i18n.language)}</dd>
                  <dt className="text-muted">{t('employees.account')}</dt>
                  <dd>{m.user?.login ?? '—'}</dd>
                  <dt className="text-muted">{t('employees.tab_documents')}</dt>
                  <dd>{m.documents}</dd>
                </dl>
              </div>
            ))}
          </div>
        </Card>
      ))}
    </div>
  )
}
