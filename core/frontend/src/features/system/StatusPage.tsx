import { useQuery } from '@tanstack/react-query'
import { Building, Database, HardDrive, Puzzle, Server, Tag, Timer } from 'lucide-react'
import type { ComponentType } from 'react'
import { useTranslation } from 'react-i18next'

import { Slot } from '../../extensions/Slot'
import { api } from '../../lib/api'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { KpiCard } from '../../components/charts'
import { PageHeader } from '../../components/layout/PageHeader'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { useMeta } from '../meta/useMeta'

interface Ready {
  status: 'ok' | 'degraded'
  version: string
  checks: { db: string; redis: string; worker: string }
}

type State = 'ok' | 'bad' | 'warn'

function stateOf(value: string | undefined): State {
  if (!value) return 'warn'
  if (value === 'ok') return 'ok'
  if (value === 'no-heartbeat' || value === 'unknown') return 'warn'
  return 'bad'
}

export function StatusPage() {
  const { t } = useTranslation()
  const meta = useMeta()
  const ready = useQuery({
    queryKey: ['ready'],
    queryFn: () => api<Ready>('/api/health/ready', undefined, [503]),
    refetchInterval: 15_000,
  })

  const checks = ready.data?.checks
  const rows: { key: string; label: string; value: string | undefined; icon: ComponentType<{ className?: string }> }[] = [
    { key: 'api', label: t('status.services.api'), value: ready.data ? 'ok' : undefined, icon: Server },
    { key: 'db', label: t('status.services.db'), value: checks?.db, icon: Database },
    { key: 'redis', label: t('status.services.redis'), value: checks?.redis, icon: HardDrive },
    { key: 'worker', label: t('status.services.worker'), value: checks?.worker, icon: Timer },
  ]

  const label = (s: State, raw?: string) =>
    s === 'ok' ? t('status.ok') : raw === 'no-heartbeat' ? t('status.noHeartbeat') : raw === 'unknown' || !raw ? t('status.unknown') : t('status.degraded')

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader title={t('status.title')} subtitle={t('status.subtitle')} />

      {ready.isError && (
        <Card className="flex items-center justify-between gap-4 p-5">
          <span className="text-sm text-danger">{t('status.error')}</span>
          <Button variant="outline" onClick={() => void ready.refetch()}>
            {t('status.retry')}
          </Button>
        </Card>
      )}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {rows.map(({ key, label: name, value, icon: Icon }) => {
          const s = stateOf(value)
          const tone = s === 'ok' ? 'var(--chart-ok)' : s === 'warn' ? 'var(--chart-late)' : 'var(--chart-absent)'
          return (
            <Card key={key} className="flex flex-col p-4">
              <div className="flex items-start justify-between">
                <span className="grid size-9 place-items-center rounded-[10px] bg-surface-2 text-muted">
                  <Icon className="size-[18px]" />
                </span>
                {ready.isLoading ? (
                  <Skeleton className="h-5 w-16" />
                ) : (
                  <span className="inline-flex items-center gap-1.5 text-xs font-medium" style={{ color: tone }}>
                    <span className="relative flex size-2">
                      {s === 'ok' && <span className="absolute inline-flex size-full animate-ping rounded-full opacity-50" style={{ background: tone }} />}
                      <span className="relative inline-flex size-2 rounded-full" style={{ background: tone }} />
                    </span>
                    {label(s, value)}
                  </span>
                )}
              </div>
              <div className="mt-5 text-[13px] text-muted">{name}</div>
            </Card>
          )
        })}
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <KpiCard icon={Tag} color="var(--c-blue)" label={t('status.version')} value={meta.data ? `v${meta.data.version}` : '—'} />
        <KpiCard icon={Building} color="var(--c-violet)" label={t('status.client')} value={meta.data?.client ?? '—'} />
        <KpiCard icon={Puzzle} color="var(--c-teal)" label={t('status.extension')} value={meta.data ? (meta.data.extension ? t('status.extensionOn') : t('status.extensionOff')) : '—'} />
      </div>

      <Card className="p-5">
        <div className="mb-3 text-[13px] text-muted">{t('status.modules')}</div>
        <div className="flex flex-wrap gap-1.5">
          {meta.isLoading && <Skeleton className="h-6 w-64" />}
          {meta.data?.modules.map((m) => (
            <Badge key={m}>{m}</Badge>
          ))}
        </div>
      </Card>

      <Slot name="status.after" />
    </div>
  )
}
