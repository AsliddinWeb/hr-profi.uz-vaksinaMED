import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { BranchMap, type MapPoint as Point } from '../../components/map/BranchMap'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { branchTitle, SEV_COLOR, type MapPoint, type Severity } from './api'

/** /pharmacy/map: butun tarmoq xaritada, rang = holat (qizil: hech kim yo'q, sariq: me'yordan kam, yashil: joyida). */
export function MapPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [hidden, setHidden] = useState<Set<Severity>>(new Set())
  const q = useQuery({ queryKey: ['pharmacy', 'map'], queryFn: () => api<MapPoint[]>('/api/v1/pharmacy/map'), refetchInterval: 60_000 })
  const points: Point[] = useMemo(
    () =>
      (q.data ?? [])
        .filter((p) => !hidden.has(p.severity))
        .map((p) => ({
          id: p.id, lat: p.lat, lng: p.lng, label: branchTitle(p), color: SEV_COLOR[p.severity],
          popup: `${branchTitle(p)}\n${t('pharmacy.severity.' + p.severity)} · ${t('pharmacy.map_here', { here: p.here_now, total: p.headcount })}${p.open_needs ? `\n${t('pharmacy.needsN', { count: p.open_needs })}` : ''}`,
        })), // fmt: skip
    [q.data, hidden, t],
  )
  const count = (s: Severity) => (q.data ?? []).filter((p) => p.severity === s).length
  const toggle = (s: Severity) => setHidden((h) => (h.has(s) ? new Set([...h].filter((x) => x !== s)) : new Set([...h, s])))

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <PageHeader title={t('pharmacy.map')} subtitle={t('pharmacy.mapSubtitle')} backTo="/pharmacy" backLabel={t('pharmacy.title')} />
      <Card className="flex flex-wrap items-center gap-3 p-3" role="group" aria-label={t('pharmacy.filter')}>
        {(['uncovered', 'short', 'ok'] as const).map((s) => (
          <button key={s} onClick={() => toggle(s)} aria-pressed={!hidden.has(s)} className={'inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm ' + (hidden.has(s) ? 'border-border text-muted line-through' : 'border-border bg-surface')}>
            <span className="size-3 rounded-full" style={{ background: SEV_COLOR[s] }} />
            {t(`pharmacy.severity.${s}`)} <span className="tabular-nums text-muted">{count(s)}</span>
          </button>
        ))}
        <span className="ml-auto text-xs text-muted">{t('pharmacy.mapHint')}</span>
      </Card>
      {q.isLoading ? <Skeleton className="h-[560px]" /> : <BranchMap points={points} height={560} onSelect={(id) => navigate(`/pharmacy/${id}`)} />}
      {q.data && q.data.length === 0 && <p className="text-center text-sm text-muted">{t('pharmacy.noGeo')}</p>}
    </div>
  )
}
