import { useQuery } from '@tanstack/react-query'
import { MapPinOff, Plus, Search, Upload, UserX } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'

import { BranchMap, type MapPoint } from '../../components/map/BranchMap'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { Pagination } from '../../components/ui/Pagination'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { useCan } from '../auth/useAuth'
import type { BranchPage, BranchPoint } from './api'

const SIZE = 25

export function BranchesPage() {
  const { t } = useTranslation()
  const can = useCan()
  const manage = can('branches.manage')
  const [view, setView] = useState<'list' | 'map'>('list')
  const [q, setQ] = useState('')
  const [noManager, setNoManager] = useState(false)
  const [noGeo, setNoGeo] = useState(false)
  const [page, setPage] = useState(1)

  const params = new URLSearchParams({ page: String(page), size: String(SIZE) })
  if (q.trim()) params.set('q', q.trim())
  if (noManager) params.set('no_manager', 'true')
  if (noGeo) params.set('no_geo', 'true')

  const list = useQuery({
    queryKey: ['branches', 'list', q, noManager, noGeo, page],
    queryFn: () => api<BranchPage>(`/api/v1/branches?${params}`),
    placeholderData: (prev) => prev,
  })
  const points = useQuery({
    queryKey: ['branches', 'map'],
    queryFn: () => api<BranchPoint[]>('/api/v1/branches/map'),
    enabled: view === 'map',
  })
  const mapPoints: MapPoint[] = useMemo(
    () =>
      (points.data ?? []).map((p) => ({
        id: p.id,
        lat: p.latitude,
        lng: p.longitude,
        label: p.name,
        inactive: !p.is_active,
        popup: [p.number ? `№${p.number} ${p.name}` : p.name, p.manager_name, p.coordinator_name].filter(Boolean).join('\n'),
      })),
    [points.data],
  )

  const s = list.data?.summary

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <PageHeader
        title={t('branches.title')}
        subtitle={t('branches.subtitle')}
        actions={
          manage && (
            <>
              <Link to="/branches/import">
                <Button variant="outline">
                  <Upload className="size-4" />
                  {t('branches.import')}
                </Button>
              </Link>
              <Link to="/branches/new">
                <Button>
                  <Plus className="size-4" />
                  {t('branches.add')}
                </Button>
              </Link>
            </>
          )
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat tint="lilac" label={t('branches.statTotal')} value={s?.total} />
        <Stat tint="mint" label={t('branches.statManager')} value={s?.with_manager} of={s?.total} />
        <Stat tint="sand" label={t('branches.statGeo')} value={s?.with_geo} of={s?.total} />
      </div>

      <Card className="flex flex-wrap items-center gap-3 p-4">
        <label className="relative min-w-36 max-w-64 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
          <Input
            className="pl-9"
            placeholder={t('branches.search')}
            value={q}
            onChange={(e) => {
              setQ(e.target.value)
              setPage(1)
            }}
            aria-label={t('branches.search')}
          />
        </label>
        <Chip active={noManager} onClick={() => (setNoManager((v) => !v), setPage(1))}>
          <UserX className="size-3.5" /> {t('branches.noManager')}
        </Chip>
        <Chip active={noGeo} onClick={() => (setNoGeo((v) => !v), setPage(1))}>
          <MapPinOff className="size-3.5" /> {t('branches.noGeo')}
        </Chip>
        <div className="ml-auto flex rounded-control bg-(--seg-bg) p-0.5 text-[13px]">
          {(['list', 'map'] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={view === v ? 'rounded-lg bg-(--seg-on) px-3 py-1.5 font-medium text-text shadow-card' : 'rounded-lg px-3 py-1.5 text-muted transition-colors hover:text-text'}
            >
              {t(`branches.view.${v}`)}
            </button>
          ))}
        </div>
      </Card>

      {view === 'map' ? (
        <>
          {points.isLoading ? <Skeleton className="h-[480px]" /> : <BranchMap points={mapPoints} height={520} />}
          {points.data && points.data.length === 0 && <p className="text-center text-sm text-muted">{t('branches.noPoints')}</p>}
        </>
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border text-xs text-muted">
                <tr>
                  <th className="px-5 py-2.5 font-medium">{t('branches.name')}</th>
                  <th className="hidden px-5 py-2.5 font-medium md:table-cell">{t('branches.manager')}</th>
                  <th className="hidden px-5 py-2.5 font-medium lg:table-cell">{t('branches.coordinator')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('branches.location')}</th>
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
                {list.data?.items.map((b) => (
                  <tr key={b.id} className={b.is_active ? '' : 'opacity-60'}>
                    <td className="px-5 py-2.5">
                      <div className="flex items-center gap-2.5">
                        {b.number !== null && <span className="rounded-md bg-surface-2 px-1.5 py-0.5 text-xs font-semibold">№{b.number}</span>}
                        <div className="min-w-0">
                          <Link to={`/branches/${b.id}/edit`} className="block truncate font-medium hover:text-primary hover:underline">
                            {b.name}
                          </Link>
                          <div className="truncate text-xs text-muted">{[b.district, b.address].filter(Boolean).join(' · ') || '—'}</div>
                        </div>
                      </div>
                    </td>
                    <td className="hidden px-5 py-2.5 md:table-cell">{b.manager_name ?? <span className="text-warning">{t('branches.noManagerShort')}</span>}</td>
                    <td className="hidden px-5 py-2.5 text-muted lg:table-cell">{b.coordinator_name ?? '—'}</td>
                    <td className="px-5 py-2.5">
                      {b.latitude !== null ? <Badge tone="success">{b.geofence_radius_m} m</Badge> : <Badge tone="warning">{t('branches.noGeoShort')}</Badge>}
                    </td>
                    <td className="px-5 py-2.5 text-right">
                      <Link to={`/branches/${b.id}/edit`}>
                        <Button variant="ghost" className="h-8 px-2">
                          {manage ? t('common.edit') : t('common.view')}
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
      )}
    </div>
  )
}

function Stat({ tint, label, value, of }: { tint: 'lilac' | 'mint' | 'sand'; label: string; value?: number; of?: number }) {
  return (
    <Card tint={tint} className="p-5">
      <div className="text-sm text-muted">{label}</div>
      <div className="mt-2 text-3xl font-semibold tabular-nums">
        {value ?? '—'}
        {of !== undefined && value !== undefined && <span className="ml-1 text-base font-normal text-muted">/ {of}</span>}
      </div>
    </Card>
  )
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      className={
        'inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium ' +
        (active ? 'border-primary bg-primary text-primary-fg' : 'border-border bg-surface text-muted hover:text-text')
      }
    >
      {children}
    </button>
  )
}
