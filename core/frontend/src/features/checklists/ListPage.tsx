import { useQuery } from '@tanstack/react-query'
import { MapPin, Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Select } from '../../components/ui/Input'
import { Pagination } from '../../components/ui/Pagination'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { useCan } from '../auth/useAuth'
import { scoreText, scoreTone, type VisitPage } from './api'

const SIZE = 25
type Scope = 'mine' | 'all' | 'branch'

/** /checklists: tekshiruvlar ro'yxati (mening / hammasi / mening filialim). */
export function ListPage() {
  const { t, i18n } = useTranslation()
  const can = useCan()
  const all = can('checklists.read') || can('checklists.manage')
  const doer = can('checklists.own') || can('checklists.manage')
  const [scope, setScope] = useState<Scope>(doer ? 'mine' : 'branch')
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const params = new URLSearchParams({ scope, page: String(page), size: String(SIZE) })
  if (status) params.set('status', status)
  const q = useQuery({ queryKey: ['checklists', 'list', params.toString()], queryFn: () => api<VisitPage>(`/api/v1/checklists/visits?${params}`), placeholderData: (p) => p })
  const scopes: Scope[] = [...(doer ? (['mine'] as const) : []), 'branch', ...(all ? (['all'] as const) : [])]

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <PageHeader
        title={t('checklists.title')}
        subtitle={t('checklists.subtitle')}
        actions={
          doer && (
            <Link to="/checklists/new">
              <Button>
                <Plus className="size-4" />
                {t('checklists.start')}
              </Button>
            </Link>
          )
        }
      />
      <div className="flex flex-wrap items-center gap-3 rounded-card bg-surface p-3 shadow-card">
        <div className="flex rounded-control bg-(--seg-bg) p-0.5 text-[13px]" role="group">
          {scopes.map((s) => (
            <button key={s} onClick={() => (setScope(s), setPage(1))} aria-pressed={scope === s} className={scope === s ? 'rounded-lg bg-(--seg-on) px-3 py-1.5 font-medium text-text shadow-card' : 'rounded-lg px-3 py-1.5 text-muted transition-colors hover:text-text'}>
              {t(`checklists.scope.${s}`)}
            </button>
          ))}
        </div>
        {scope !== 'branch' && (
          <Select className="w-auto" value={status} onChange={(e) => (setStatus(e.target.value), setPage(1))} aria-label={t('attendance.statusLabel')}>
            <option value="">{t('attendance.allStatuses')}</option>
            <option value="draft">{t('checklists.status.draft')}</option>
            <option value="submitted">{t('checklists.status.submitted')}</option>
          </Select>
        )}
      </div>
      {q.isLoading ? (
        <Skeleton className="h-48" />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border text-xs text-muted">
                <tr>
                  <th className="px-5 py-2.5 font-medium">{t('checklists.branch')}</th>
                  <th className="hidden px-5 py-2.5 font-medium md:table-cell">{t('checklists.coordinator')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('attendance.statusLabel')}</th>
                  <th className="px-5 py-2.5 text-right font-medium">{t('checklists.score')}</th>
                  <th className="hidden px-5 py-2.5 font-medium sm:table-cell">{t('checklists.date')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {q.data?.items.map((v) => (
                  <tr key={v.id}>
                    <td className="px-5 py-2.5">
                      <Link to={v.status === 'draft' && v.coordinator ? `/checklists/${v.id}/fill` : `/checklists/${v.id}`} className="font-medium hover:text-primary hover:underline">
                        {v.branch?.name ?? '—'}
                      </Link>
                      <div className="mt-0.5 flex items-center gap-1 text-xs text-muted">
                        {v.template.name}
                        {!v.geo_ok && (
                          <span className="inline-flex items-center gap-0.5 text-warning" title={t('checklists.outside')}>
                            <MapPin className="size-3" />
                            {v.distance_m} m
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="hidden px-5 py-2.5 text-muted md:table-cell">{v.coordinator?.name ?? '—'}</td>
                    <td className="px-5 py-2.5">
                      <Badge tone={v.status === 'draft' ? 'warning' : 'success'}>{t(`checklists.status.${v.status}`)}</Badge>
                      {v.status === 'draft' && <span className="ml-1.5 text-xs text-muted tabular-nums">{v.answered}/{v.total}</span>}
                    </td>
                    <td className="px-5 py-2.5 text-right">
                      {v.status === 'submitted' ? <Badge tone={scoreTone(v.score)}>{scoreText(v.score)}</Badge> : '—'}
                      {v.critical_fails > 0 && <span className="ml-1.5 text-xs font-semibold text-danger" title={t('checklists.critical')}>!{v.critical_fails}</span>}
                    </td>
                    <td className="hidden px-5 py-2.5 tabular-nums text-muted sm:table-cell">{formatDateTime(v.submitted_at ?? v.started_at, i18n.language)}</td>
                  </tr>
                ))}
                {q.data && q.data.items.length === 0 && (
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
      )}
      {q.data && q.data.total > SIZE && <Pagination page={page} size={SIZE} total={q.data.total} onPage={setPage} />}
    </div>
  )
}
