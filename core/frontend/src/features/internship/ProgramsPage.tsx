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
import type { Program } from './api'

/** /internship/programs: stajirovka dasturlari. */
export function ProgramsPage() {
  const { t } = useTranslation()
  const manage = useCan()('internship.manage')
  const q = useQuery({ queryKey: ['internship', 'programs', 'all'], queryFn: () => api<Program[]>('/api/v1/internship/programs?all=true') })
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title={t('internship.programs.title')}
        subtitle={t('internship.programs.subtitle')}
        backTo="/internship"
        backLabel={t('internship.title')}
        actions={
          manage && (
            <Link to="/internship/programs/new">
              <Button>
                <Plus className="size-4" />
                {t('internship.programs.add')}
              </Button>
            </Link>
          )
        }
      />
      {!q.data ? (
        <Skeleton className="h-48" />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {q.data.map((p) => (
            <Link key={p.id} to={`/internship/programs/${p.id}`}>
              <Card className="flex h-full flex-col gap-2 p-5 transition-shadow hover:shadow-card">
                <div className="flex items-start justify-between gap-3">
                  <h2 className="font-semibold">{p.name}</h2>
                  {!p.is_active && <Badge>{t('needs.categories.inactive')}</Badge>}
                </div>
                {p.description && <p className="text-sm text-muted">{p.description}</p>}
                <p className="mt-auto text-sm tabular-nums text-muted">
                  {t('internship.programs.stepsN', { count: p.steps })} · {t('internship.programs.enrolledN', { count: p.enrolled })}
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
