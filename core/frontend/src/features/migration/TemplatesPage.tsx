import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { MigrationTabs } from './MigrationTabs'
import type { Template } from './api'

/** /migration/templates: saqlangan ustun moslashtirishlari. */
export function TemplatesPage() {
  const { t } = useTranslation()
  const q = useQuery({ queryKey: ['migration', 'templates'], queryFn: () => api<Template[]>('/api/v1/migration/templates') })
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title={t('migration.title')}
        subtitle={t('migration.templatesHint')}
        actions={
          <Link to="/migration/templates/new">
            <Button>
              <Plus className="size-4" />
              {t('migration.tpl.add')}
            </Button>
          </Link>
        }
      />
      <MigrationTabs />
      {!q.data ? (
        <Skeleton className="h-40" />
      ) : (
        <Card className="overflow-hidden">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs text-muted">
              <tr>
                <th className="px-5 py-2.5 font-medium">{t('migration.tpl.name')}</th>
                <th className="px-5 py-2.5 font-medium">{t('migration.new.dataset')}</th>
                <th className="px-5 py-2.5 text-right font-medium">{t('migration.tpl.fields')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {q.data.map((x) => (
                <tr key={x.id}>
                  <td className="px-5 py-2.5">
                    <Link to={`/migration/templates/${x.id}/edit`} className="font-medium hover:text-primary hover:underline">
                      {x.name}
                    </Link>
                  </td>
                  <td className="px-5 py-2.5 text-muted">{t(`migration.dataset.${x.dataset}`)}</td>
                  <td className="px-5 py-2.5 text-right tabular-nums text-muted">{Object.keys(x.mapping).length}</td>
                </tr>
              ))}
              {q.data.length === 0 && (
                <tr>
                  <td colSpan={3} className="px-5 py-10 text-center text-muted">
                    {t('common.empty')}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  )
}
