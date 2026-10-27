import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Select } from '../../components/ui/Input'
import { Pagination } from '../../components/ui/Pagination'
import { Skeleton } from '../../components/ui/Skeleton'
import { api, send } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { useCan } from '../auth/useAuth'
import { branchTitle, type Need } from './api'

const SIZE = 50

/** /pharmacy/needs: «Xodim kerak» so'rovlari va me'yordan kam filiallar bo'yicha takliflar. */
export function NeedsPage() {
  const { t, i18n } = useTranslation()
  const can = useCan()
  const [params] = useSearchParams()
  const branchId = params.get('branch')
  const [status, setStatus] = useState('open')
  const [page, setPage] = useState(1)
  const qs = new URLSearchParams({ status, page: String(page), size: String(SIZE) })
  if (branchId) qs.set('branch_id', branchId)
  const list = useQuery({ queryKey: ['pharmacy', 'needs', qs.toString()], queryFn: () => api<{ total: number; items: Need[] }>(`/api/v1/pharmacy/needs?${qs}`), placeholderData: (p) => p })
  const canRequest = can('pharmacy.request') || can('pharmacy.manage')
  const sug = useQuery({ queryKey: ['pharmacy', 'suggestions'], queryFn: () => api<{ branch: { id: number; number: number | null; name: string }; role: string; gap: number }[]>('/api/v1/pharmacy/needs/suggestions'), enabled: canRequest })
  const qc = useQueryClient()
  const quick = useMutation({
    mutationFn: (s: { branch: { id: number }; role: string; gap: number }) => send('POST', '/api/v1/pharmacy/needs', { branch_id: s.branch.id, role: s.role, count: s.gap, urgency: 'normal', reason: t('pharmacy.needs.autoReason') }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['pharmacy'] }),
  })

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader
        title={t('pharmacy.needs.title')}
        subtitle={t('pharmacy.needs.subtitle')}
        backTo="/pharmacy"
        backLabel={t('pharmacy.title')}
        actions={
          canRequest && (
            <Link to="/pharmacy/needs/new">
              <Button>
                <Plus className="size-4" />
                {t('pharmacy.needs.add')}
              </Button>
            </Link>
          )
        }
      />
      {sug.data && sug.data.length > 0 && (
        <Card tint="sand" className="p-5">
          <h2 className="font-semibold">{t('pharmacy.needs.suggest')}</h2>
          <p className="text-xs text-muted">{t('pharmacy.needs.suggestHint')}</p>
          <ul className="mt-3 divide-y divide-border/60 text-sm">
            {sug.data.slice(0, 10).map((s) => (
              <li key={`${s.branch.id}-${s.role}`} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span>
                  <Link to={`/pharmacy/${s.branch.id}`} className="font-medium hover:underline">
                    {branchTitle(s.branch)}
                  </Link>{' '}
                  — {t(`pharmacy.roles.${s.role}`)} × {s.gap}
                </span>
                <Button variant="outline" className="h-8" disabled={quick.isPending} onClick={() => quick.mutate(s)}>
                  {t('pharmacy.needs.create')}
                </Button>
              </li>
            ))}
          </ul>
        </Card>
      )}
      <Card className="flex items-center gap-3 p-3">
        <Select className="w-auto" value={status} onChange={(e) => (setStatus(e.target.value), setPage(1))} aria-label={t('attendance.statusLabel')}>
          {['open', 'filled', 'cancelled', 'all'].map((s) => (
            <option key={s} value={s}>
              {t(`pharmacy.needs.status.${s}`)}
            </option>
          ))}
        </Select>
        {branchId && (
          <Link to="/pharmacy/needs" className="text-sm text-primary hover:underline">
            {t('pharmacy.needs.allBranches')}
          </Link>
        )}
      </Card>
      {list.isLoading ? (
        <Skeleton className="h-40" />
      ) : (
        <Card className="overflow-hidden">
          <ul className="divide-y divide-border text-sm">
            {list.data?.items.map((n) => (
              <li key={n.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5">
                <div className="min-w-0">
                  <Link to={`/pharmacy/needs/${n.id}`} className="font-medium hover:text-primary hover:underline">
                    {n.branch ? branchTitle(n.branch) : '—'} — {t(`pharmacy.roles.${n.role}`)} × {n.count}
                  </Link>
                  <div className="text-xs text-muted">
                    {n.created_by} · {formatDate(n.created_at, i18n.language)}
                    {n.needed_from && ` · ${t('pharmacy.needs.from', { date: formatDate(n.needed_from, i18n.language) })}`}
                  </div>
                </div>
                <div className="flex gap-1.5">
                  {n.approval !== 'approved' && <Badge tone={n.approval === 'rejected' ? 'danger' : 'warning'}>{t(`pharmacy.needs.approval.${n.approval}`)}</Badge>}
                  <Badge tone={n.urgency === 'urgent' ? 'danger' : 'neutral'}>{t(`pharmacy.urgency.${n.urgency}`)}</Badge>
                  <Badge tone={n.status === 'open' ? 'warning' : n.status === 'filled' ? 'success' : 'neutral'}>{t(`pharmacy.needs.status.${n.status}`)}</Badge>
                </div>
              </li>
            ))}
            {list.data?.items.length === 0 && <li className="px-5 py-10 text-center text-muted">{t('common.empty')}</li>}
          </ul>
        </Card>
      )}
      {list.data && list.data.total > SIZE && <Pagination page={page} size={SIZE} total={list.data.total} onPage={setPage} />}
    </div>
  )
}
