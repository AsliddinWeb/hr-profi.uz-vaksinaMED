import { useQuery } from '@tanstack/react-query'
import { Pencil, Plus, Split } from 'lucide-react'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { useCan } from '../auth/useAuth'
import type { DepartmentRow } from './api'
import { orderTree } from './tree'

export function DepartmentsPage() {
  const { t } = useTranslation()
  const can = useCan()
  const manage = can('org.manage')
  const list = useQuery({ queryKey: ['org', 'departments'], queryFn: () => api<DepartmentRow[]>('/api/v1/org/departments') })
  const rows = useMemo(() => orderTree(list.data ?? []), [list.data])

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <PageHeader
        title={t('org.departmentsTitle')}
        subtitle={t('org.departmentsSubtitle')}
        actions={
          manage && (
            <Link to="/org/departments/new">
              <Button>
                <Plus className="size-4" />
                {t('org.addDepartment')}
              </Button>
            </Link>
          )
        }
      />

      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs text-muted">
              <tr>
                <th className="px-5 py-2.5 font-medium">{t('org.name')}</th>
                <th className="px-5 py-2.5 font-medium">{t('org.head')}</th>
                <th className="hidden px-5 py-2.5 font-medium md:table-cell">{t('org.positions')}</th>
                <th className="hidden px-5 py-2.5 font-medium md:table-cell">{t('branches.title')}</th>
                <th className="px-5 py-2.5" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {list.isLoading && (
                <tr>
                  <td colSpan={5} className="px-5 py-2.5">
                    <Skeleton className="h-24" />
                  </td>
                </tr>
              )}
              {rows.map((d) => (
                <tr key={d.id} className={d.is_active ? '' : 'opacity-60'}>
                  <td className="px-5 py-2.5">
                    <div className="flex items-center gap-2.5" style={{ paddingLeft: (d.depth - 1) * 20 }}>
                      <span className="size-3 shrink-0 rounded-full" style={{ background: d.color ?? 'var(--primary)' }} />
                      <Link to={`/org/departments/${d.id}/edit`} className="font-medium hover:text-primary hover:underline">
                        {d.name}
                      </Link>
                      {!d.is_active && <Badge tone="warning">{t('org.inactive')}</Badge>}
                    </div>
                  </td>
                  <td className="px-5 py-2.5">{d.head?.full_name ?? <span className="text-warning">{t('org.noHead')}</span>}</td>
                  <td className="hidden px-5 py-2.5 text-muted md:table-cell">{d.positions}</td>
                  <td className="hidden px-5 py-2.5 text-muted md:table-cell">{d.branches}</td>
                  <td className="px-5 py-2.5">
                    <div className="flex justify-end gap-1">
                      {manage && (
                        <Link to={`/org/departments/new?parent=${d.id}`} title={t('org.addChild')} aria-label={t('org.addChild')}>
                          <Button variant="ghost" className="h-8 px-2">
                            <Split className="size-4" />
                          </Button>
                        </Link>
                      )}
                      <Link to={`/org/departments/${d.id}/edit`} title={t('common.edit')} aria-label={t('common.edit')}>
                        <Button variant="ghost" className="h-8 px-2">
                          <Pencil className="size-4" />
                        </Button>
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
              {list.data && rows.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-5 py-10 text-center text-muted">
                    {t('common.empty')}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
