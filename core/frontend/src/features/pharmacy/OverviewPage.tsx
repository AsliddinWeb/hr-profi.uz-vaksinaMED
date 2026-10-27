import { useQuery } from '@tanstack/react-query'
import { Map as MapIcon, Search, SlidersHorizontal, ClipboardList, ShieldCheck } from 'lucide-react'
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
import { useCan } from '../auth/useAuth'
import { SeverityBadge } from './SeverityBadge'
import { branchTitle, ROLES, type Overview } from './api'

const SIZE = 50
const ONLY = ['uncovered', 'short', 'needs', 'ok'] as const

/** /pharmacy: tarmoq holati: har filialning jamoasi me'yor bilan, bugungi davomat va «xodim kerak». */
export function OverviewPage() {
  const { t } = useTranslation()
  const can = useCan()
  const [q, setQ] = useState('')
  const [district, setDistrict] = useState('')
  const [only, setOnly] = useState('')
  const [page, setPage] = useState(1)
  const params = new URLSearchParams({ page: String(page), size: String(SIZE) })
  if (q.trim()) params.set('q', q.trim())
  if (district) params.set('district', district)
  if (only) params.set('only', only)
  const data = useQuery({ queryKey: ['pharmacy', 'overview', params.toString()], queryFn: () => api<Overview>(`/api/v1/pharmacy/overview?${params}`), placeholderData: (p) => p, refetchInterval: 60_000 })
  const d = data.data
  const k = d?.kpis
  const reset = (fn: () => void) => (fn(), setPage(1))

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-5">
      <PageHeader
        title={t('pharmacy.title')}
        subtitle={t('pharmacy.subtitle')}
        actions={
          <>
            <Link to="/pharmacy/map">
              <Button variant="outline">
                <MapIcon className="size-4" />
                {t('pharmacy.map')}
              </Button>
            </Link>
            <Link to="/pharmacy/needs">
              <Button variant="outline">
                <ClipboardList className="size-4" />
                {t('pharmacy.needs.title')}
              </Button>
            </Link>
            {(can('pharmacy.manage') || can('pharmacy.read')) && (
              <Link to="/pharmacy/quality">
                <Button variant="outline">
                  <ShieldCheck className="size-4" />
                  {t('pharmacy.quality.title')}
                </Button>
              </Link>
            )}
            {can('pharmacy.manage') && (
              <Link to="/pharmacy/norms">
                <Button variant="outline">
                  <SlidersHorizontal className="size-4" />
                  {t('pharmacy.norms.title')}
                </Button>
              </Link>
            )}
          </>
        }
      />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-6">
        <Kpi tint="lilac" label={t('pharmacy.kpi.branches')} value={k?.branches} />
        <Kpi tint="rose" label={t('pharmacy.severity.uncovered')} value={k?.uncovered} hint={t('pharmacy.kpi.uncoveredHint')} />
        <Kpi tint="sand" label={t('pharmacy.severity.short')} value={k?.short} hint={t('pharmacy.kpi.shortHint')} />
        <Kpi tint="mint" label={t('pharmacy.severity.ok')} value={k?.ok} />
        <Kpi label={t('pharmacy.kpi.needs')} value={k?.open_needs} hint={k ? t('pharmacy.kpi.needsBranches', { count: k.with_needs }) : undefined} />
        <Kpi label={t('pharmacy.kpi.today')} value={k ? `${k.attended}/${k.expected}` : undefined} hint={k ? t('pharmacy.kpi.todayHint', { late: k.late, absent: k.absent }) : undefined} />
      </div>
      <Card className="flex flex-wrap items-center gap-3 p-4">
        <label className="relative min-w-36 max-w-64 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
          <Input className="pl-9" placeholder={t('pharmacy.search')} value={q} onChange={(e) => reset(() => setQ(e.target.value))} aria-label={t('pharmacy.search')} />
        </label>
        <Select className="w-auto" value={district} onChange={(e) => reset(() => setDistrict(e.target.value))} aria-label={t('branches.district')}>
          <option value="">{t('pharmacy.allDistricts')}</option>
          {d?.districts.map((x) => (
            <option key={x} value={x}>
              {x}
            </option>
          ))}
        </Select>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label={t('pharmacy.filter')}>
          {ONLY.map((o) => (
            <button key={o} onClick={() => reset(() => setOnly(only === o ? '' : o))} aria-pressed={only === o} className={'rounded-full border px-3 py-1.5 text-xs font-medium ' + (only === o ? 'border-primary bg-primary text-primary-fg' : 'border-border bg-surface text-muted hover:text-text')}>
              {t(`pharmacy.only.${o}`)}
            </button>
          ))}
        </div>
      </Card>
      {!d ? (
        <Skeleton className="h-96" />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border text-xs text-muted">
                <tr>
                  <th className="px-4 py-3 font-medium">{t('pharmacy.branch')}</th>
                  <th className="hidden px-4 py-3 font-medium lg:table-cell">{t('branches.coordinator')}</th>
                  <th className="px-4 py-3 font-medium">{t('pharmacy.team')}</th>
                  <th className="px-4 py-3 font-medium">{t('pharmacy.todayCol')}</th>
                  <th className="px-4 py-3 font-medium">{t('attendance.statusLabel')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {d.items.map((b) => (
                  <tr key={b.id}>
                    <td className="px-4 py-3">
                      <Link to={`/pharmacy/${b.id}`} className="font-medium hover:text-primary hover:underline">
                        {branchTitle(b)}
                      </Link>
                      <div className="text-xs text-muted">{b.district ?? '—'}</div>
                    </td>
                    <td className="hidden px-4 py-3 text-muted lg:table-cell">{b.coordinator?.name ?? '—'}</td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1.5 tabular-nums">
                        {ROLES.filter((r) => b.norm[r] > 0 || b.counts[r] > 0).map((r) => (
                          <span key={r} className={'rounded-md px-1.5 py-0.5 text-xs ' + (b.gaps[r] ? 'bg-warning/20 text-warning' : 'bg-surface-2 text-muted')} title={t(`pharmacy.roles.${r}`)}>
                            {t(`pharmacy.roleShort.${r}`)} {b.counts[r]}/{b.norm[r]}
                          </span>
                        ))}
                        {b.headcount === 0 && <span className="text-xs text-muted">{t('pharmacy.noStaff')}</span>}
                      </div>
                    </td>
                    <td className="px-4 py-3 tabular-nums">
                      <span className="font-medium">{b.today.here_now}</span>
                      <span className="text-muted"> / {b.today.expected}</span>
                      {(b.today.late > 0 || b.today.absent > 0) && (
                        <div className="text-xs text-muted">
                          {b.today.late > 0 && <span className="text-warning">{t('pharmacy.lateN', { count: b.today.late })} </span>}
                          {b.today.absent > 0 && <span className="text-danger">{t('pharmacy.absentN', { count: b.today.absent })}</span>}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <SeverityBadge severity={b.severity} />
                        {b.open_needs > 0 && <Badge>{t('pharmacy.needsN', { count: b.open_needs })}</Badge>}
                      </div>
                    </td>
                  </tr>
                ))}
                {d.items.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-10 text-center text-muted">
                      {t('common.empty')}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="border-t border-border px-5 py-2.5">
            <Pagination page={page} size={SIZE} total={d.total} onPage={setPage} />
          </div>
        </Card>
      )}
    </div>
  )
}

function Kpi({ label, value, hint, tint }: { label: string; value?: number | string; hint?: string; tint?: 'rose' | 'lilac' | 'mint' | 'sand' }) {
  return (
    <Card tint={tint} className="p-4">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1.5 text-2xl font-semibold tabular-nums">{value ?? '—'}</div>
      {hint && <div className="mt-1 text-[11px] text-muted">{hint}</div>}
    </Card>
  )
}
