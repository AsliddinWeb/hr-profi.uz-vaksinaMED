import { useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input, Select } from '../../components/ui/Input'
import { Pagination } from '../../components/ui/Pagination'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import type { FaceList, FaceState } from './api'

const SIZE = 50
const TONE: Record<FaceState, 'success' | 'warning' | 'neutral' | 'danger'> = { enrolled: 'success', consent_only: 'warning', none: 'neutral', revoked: 'danger' }

/** /face/admin: xodimlarning Face ID holati (faqat holat: shablon va rasm ko'rsatilmaydi). */
export function AdminPage() {
  const { t, i18n } = useTranslation()
  const [q, setQ] = useState('')
  const [state, setState] = useState('')
  const [page, setPage] = useState(1)
  const params = new URLSearchParams({ page: String(page), size: String(SIZE) })
  if (q.trim()) params.set('q', q.trim())
  if (state) params.set('state', state)
  const list = useQuery({ queryKey: ['face', 'list', params.toString()], queryFn: () => api<FaceList>(`/api/v1/face/employees?${params}`), placeholderData: (p) => p })
  const s = list.data?.summary

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader title={t('face.admin.title')} subtitle={t('face.admin.subtitle')} />
      <div className="grid gap-4 sm:grid-cols-3">
        <Card tint="mint" className="p-5">
          <div className="text-sm text-muted">{t('face.admin.statEnrolled')}</div>
          <div className="mt-2 text-3xl font-semibold tabular-nums">{s?.enrolled ?? '—'}</div>
        </Card>
        <Card tint="lilac" className="p-5">
          <div className="text-sm text-muted">{t('face.admin.statActive')}</div>
          <div className="mt-2 text-3xl font-semibold tabular-nums">{s?.active ?? '—'}</div>
        </Card>
        <Card tint="sand" className="p-5">
          <div className="text-sm text-muted">{t('face.admin.statCoverage')}</div>
          <div className="mt-2 text-3xl font-semibold tabular-nums">{s && s.active ? Math.round((s.enrolled / s.active) * 100) : 0}%</div>
        </Card>
      </div>
      <Card className="flex flex-wrap items-center gap-3 p-4">
        <label className="relative min-w-36 max-w-64 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
          <Input className="pl-9" placeholder={t('schedule.searchEmployee')} value={q} onChange={(e) => (setQ(e.target.value), setPage(1))} aria-label={t('schedule.searchEmployee')} />
        </label>
        <Select className="w-auto" value={state} onChange={(e) => (setState(e.target.value), setPage(1))} aria-label={t('attendance.statusLabel')}>
          <option value="">{t('attendance.allStatuses')}</option>
          {(['enrolled', 'consent_only', 'revoked', 'none'] as const).map((k) => (
            <option key={k} value={k}>
              {t(`face.state.${k}`)}
            </option>
          ))}
        </Select>
      </Card>
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs text-muted">
              <tr>
                <th className="px-5 py-2.5 font-medium">{t('employees.fullName')}</th>
                <th className="px-5 py-2.5 font-medium">{t('attendance.statusLabel')}</th>
                <th className="hidden px-5 py-2.5 font-medium md:table-cell">{t('face.admin.consent')}</th>
                <th className="hidden px-5 py-2.5 font-medium lg:table-cell">{t('face.admin.lastVerified')}</th>
                <th className="px-5 py-2.5" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {list.isLoading && (
                <tr>
                  <td colSpan={5} className="px-5 py-2.5">
                    <Skeleton className="h-28" />
                  </td>
                </tr>
              )}
              {list.data?.items.map((r) => (
                <tr key={r.employee.id}>
                  <td className="px-5 py-2.5">
                    <Link to={`/face/admin/${r.employee.id}`} className="font-medium hover:text-primary hover:underline">
                      {r.employee.full_name}
                    </Link>
                  </td>
                  <td className="px-5 py-2.5">
                    <Badge tone={TONE[r.state]}>{t(`face.state.${r.state}`)}</Badge>
                  </td>
                  <td className="hidden px-5 py-2.5 text-muted md:table-cell">{r.given_at ? formatDateTime(r.given_at, i18n.language) : '—'}</td>
                  <td className="hidden px-5 py-2.5 text-muted lg:table-cell">{r.last_verified_at ? formatDateTime(r.last_verified_at, i18n.language) : '—'}</td>
                  <td className="px-5 py-2.5 text-right">
                    <Link to={`/face/admin/${r.employee.id}`}>
                      <Button variant="ghost" className="h-8 px-2">
                        {t('common.view')}
                      </Button>
                    </Link>
                  </td>
                </tr>
              ))}
              {list.data && list.data.items.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-5 py-10 text-center text-muted">
                    {t('common.empty')}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {list.data && (
          <div className="border-t border-border px-5 py-2.5">
            <Pagination page={page} size={SIZE} total={list.data.total} onPage={setPage} />
          </div>
        )}
      </Card>
    </div>
  )
}
