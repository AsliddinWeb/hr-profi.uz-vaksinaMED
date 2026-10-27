import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { Input, Select } from '../../components/ui/Input'
import { Pagination } from '../../components/ui/Pagination'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { addDays, todayLocal } from '../attendance/api'
import { MobileTabs } from './MobileTabs'
import type { Page, Session } from './api'

const SIZE = 25

/** /mobile/sessions: ish kuni sessiyalari tarixi. */
export function SessionsPage() {
  const { t, i18n } = useTranslation()
  const today = todayLocal()
  const [range, setRange] = useState({ start: addDays(today, -13), end: today })
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const params = new URLSearchParams({ ...range, page: String(page), size: String(SIZE) })
  if (status) params.set('status', status)
  const q = useQuery({ queryKey: ['mobile', 'sessions', params.toString()], queryFn: () => api<Page<Session>>(`/api/v1/mobile/sessions?${params}`), placeholderData: (p) => p })
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <PageHeader title={t('mobile.title')} subtitle={t('mobile.subtitle')} />
      <MobileTabs />
      <div className="flex flex-wrap items-center gap-3 rounded-card bg-surface p-3 shadow-card">
        <Input type="date" className="w-40" value={range.start} max={range.end} onChange={(e) => e.target.value && (setRange({ ...range, start: e.target.value }), setPage(1))} aria-label={t('schedule.apply.from')} />
        <span className="text-muted">–</span>
        <Input type="date" className="w-40" value={range.end} min={range.start} onChange={(e) => e.target.value && (setRange({ ...range, end: e.target.value }), setPage(1))} aria-label={t('schedule.apply.to')} />
        <Select className="w-auto" value={status} onChange={(e) => (setStatus(e.target.value), setPage(1))} aria-label={t('attendance.statusLabel')}>
          <option value="">{t('attendance.allStatuses')}</option>
          {(['active', 'ended', 'auto_closed'] as const).map((s) => (
            <option key={s} value={s}>
              {t(`mobile.session.status.${s}`)}
            </option>
          ))}
        </Select>
      </div>
      {!q.data ? (
        <Skeleton className="h-48" />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border text-xs text-muted">
                <tr>
                  <th className="px-5 py-2.5 font-medium">{t('payroll.line.employee')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('mobile.session.started')}</th>
                  <th className="hidden px-5 py-2.5 font-medium sm:table-cell">{t('mobile.session.ended')}</th>
                  <th className="px-5 py-2.5 text-right font-medium">km</th>
                  <th className="px-5 py-2.5 font-medium">{t('attendance.statusLabel')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border tabular-nums">
                {q.data.items.map((s) => (
                  <tr key={s.id}>
                    <td className="px-5 py-2.5">
                      <Link to={`/mobile/sessions/${s.id}`} className="font-medium hover:text-primary hover:underline">
                        {s.employee?.name}
                      </Link>
                    </td>
                    <td className="px-5 py-2.5 text-muted">{formatDateTime(s.started_at, i18n.language)}</td>
                    <td className="hidden px-5 py-2.5 text-muted sm:table-cell">{formatDateTime(s.ended_at, i18n.language)}</td>
                    <td className="px-5 py-2.5 text-right">{s.distance_km.toFixed(1)}</td>
                    <td className="px-5 py-2.5">
                      <Badge tone={s.status === 'active' ? 'warning' : s.status === 'auto_closed' ? 'danger' : 'success'}>{t(`mobile.session.status.${s.status}`)}</Badge>
                    </td>
                  </tr>
                ))}
                {q.data.items.length === 0 && (
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
