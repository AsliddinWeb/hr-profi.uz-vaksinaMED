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
import type { Category } from './api'

/** /needs/categories: kategoriyalar ro'yxati (yaratish/tahrirlash alohida sahifada). */
export function CategoriesPage() {
  const { t } = useTranslation()
  const q = useQuery({ queryKey: ['needs', 'categories', 'all'], queryFn: () => api<Category[]>('/api/v1/needs/categories?all=true') })
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title={t('needs.categories.title')}
        subtitle={t('needs.categories.subtitle')}
        backTo="/needs"
        backLabel={t('needs.title')}
        actions={
          <Link to="/needs/categories/new">
            <Button>
              <Plus className="size-4" />
              {t('needs.categories.add')}
            </Button>
          </Link>
        }
      />
      {!q.data ? (
        <Skeleton className="h-48" />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border text-xs text-muted">
                <tr>
                  <th className="px-5 py-2.5 font-medium">{t('needs.categories.name')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('needs.categories.defaultAssignee')}</th>
                  <th className="px-5 py-2.5 text-right font-medium">{t('needs.categories.sla')}</th>
                  <th className="px-5 py-2.5 text-right font-medium">{t('needs.categories.used')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {q.data.map((c) => (
                  <tr key={c.id}>
                    <td className="px-5 py-2.5">
                      <Link to={`/needs/categories/${c.id}/edit`} className="font-medium hover:text-primary hover:underline">
                        {c.name}
                      </Link>
                      {!c.is_active && <Badge className="ml-2">{t('needs.categories.inactive')}</Badge>}
                      {c.description && <div className="text-xs text-muted">{c.description}</div>}
                    </td>
                    <td className="px-5 py-2.5 text-muted">{c.default_assignee?.name ?? '—'}</td>
                    <td className="px-5 py-2.5 text-right tabular-nums">{c.sla_days ? t('needs.categories.days', { count: c.sla_days }) : '—'}</td>
                    <td className="px-5 py-2.5 text-right tabular-nums text-muted">{c.used}</td>
                  </tr>
                ))}
                {q.data.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-5 py-10 text-center text-muted">
                      {t('common.empty')}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}
