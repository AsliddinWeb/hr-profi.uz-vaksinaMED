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
import type { Template } from './api'

/** /checklists/templates: shablonlar ro'yxati (yaratish/tahrirlash alohida sahifada). */
export function TemplatesPage() {
  const { t } = useTranslation()
  const manage = useCan()('checklists.manage')
  const q = useQuery({ queryKey: ['checklists', 'templates', 'all'], queryFn: () => api<Template[]>('/api/v1/checklists/templates?all=true') })
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title={t('checklists.templates.title')}
        subtitle={t('checklists.templates.subtitle')}
        backTo="/checklists"
        backLabel={t('checklists.title')}
        actions={
          manage && (
            <Link to="/checklists/templates/new">
              <Button>
                <Plus className="size-4" />
                {t('checklists.templates.add')}
              </Button>
            </Link>
          )
        }
      />
      {!q.data ? (
        <Skeleton className="h-48" />
      ) : (
        <Card className="overflow-hidden">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs text-muted">
              <tr>
                <th className="px-5 py-2.5 font-medium">{t('checklists.templates.name')}</th>
                <th className="px-5 py-2.5 text-right font-medium">{t('checklists.templates.items')}</th>
                <th className="px-5 py-2.5 text-right font-medium">{t('checklists.templates.used')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {q.data.map((x) => (
                <tr key={x.id}>
                  <td className="px-5 py-2.5">
                    {manage ? (
                      <Link to={`/checklists/templates/${x.id}/edit`} className="font-medium hover:text-primary hover:underline">
                        {x.name}
                      </Link>
                    ) : (
                      <span className="font-medium">{x.name}</span>
                    )}
                    {!x.is_active && <Badge className="ml-2">{t('needs.categories.inactive')}</Badge>}
                    {x.description && <div className="text-xs text-muted">{x.description}</div>}
                  </td>
                  <td className="px-5 py-2.5 text-right tabular-nums">{x.item_count}</td>
                  <td className="px-5 py-2.5 text-right tabular-nums text-muted">{x.used}</td>
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
