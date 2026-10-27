import { useQuery } from '@tanstack/react-query'
import { Phone, Plus, Video } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { Pagination } from '../../components/ui/Pagination'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { useCan } from '../auth/useAuth'
import { callTitle, durationText, STATUS_TONE, type CallPage } from './api'

const SIZE = 25
type Scope = 'live' | 'mine' | 'all'

/** /calls: faol va rejalashtirilgan qo'ng'iroqlar, mening tarixim, (HR/direktor) hammasi. */
export function ListPage() {
  const { t, i18n } = useTranslation()
  const can = useCan()
  const viewer = can('calls.read') || can('calls.manage')
  const [scope, setScope] = useState<Scope>('live')
  const [text, setText] = useState('')
  const [page, setPage] = useState(1)
  const params = new URLSearchParams({ scope, page: String(page), size: String(SIZE) })
  if (text.trim()) params.set('q', text.trim())
  const list = useQuery({ queryKey: ['calls', 'list', params.toString()], queryFn: () => api<CallPage>(`/api/v1/calls?${params}`), placeholderData: (p) => p, refetchInterval: 15_000 })
  const cfg = useQuery({ queryKey: ['calls', 'config'], queryFn: () => api<{ enabled: boolean }>('/api/v1/calls/config') })
  const scopes: Scope[] = ['live', 'mine', ...(viewer ? (['all'] as const) : [])]
  const reset = <T,>(fn: (v: T) => void) => (v: T) => (fn(v), setPage(1))

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <PageHeader
        title={t('calls.title')}
        subtitle={t('calls.subtitle')}
        actions={
          <Link to="/calls/new">
            <Button>
              <Plus className="size-4" />
              {t('calls.new')}
            </Button>
          </Link>
        }
      />
      {cfg.data && !cfg.data.enabled && (
        <p role="alert" className="rounded-card border border-warning/40 bg-warning/10 p-4 text-sm">
          {t('calls.disabled')}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-3 rounded-card bg-surface p-3 shadow-card">
        <div className="flex rounded-control bg-(--seg-bg) p-0.5 text-[13px]" role="group">
          {scopes.map((s) => (
            <button key={s} onClick={() => reset(setScope)(s)} aria-pressed={scope === s} className={scope === s ? 'rounded-lg bg-(--seg-on) px-3 py-1.5 font-medium text-text shadow-card' : 'rounded-lg px-3 py-1.5 text-muted transition-colors hover:text-text'}>
              {t(`calls.scope.${s}`)}
            </button>
          ))}
        </div>
        <Input className="w-56" value={text} onChange={(e) => reset(setText)(e.target.value)} placeholder={t('calls.search')} aria-label={t('calls.search')} />
      </div>
      {list.isLoading ? (
        <Skeleton className="h-48" />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border text-xs text-muted">
                <tr>
                  <th className="px-5 py-2.5 font-medium">{t('calls.callCol')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('attendance.statusLabel')}</th>
                  <th className="hidden px-5 py-2.5 font-medium md:table-cell">{t('calls.when')}</th>
                  <th className="hidden px-5 py-2.5 text-right font-medium sm:table-cell">{t('calls.duration')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {list.data?.items.map((c) => (
                  <tr key={c.id}>
                    <td className="px-5 py-2.5">
                      <Link to={`/calls/${c.id}`} className="inline-flex items-center gap-2 font-medium hover:text-primary hover:underline">
                        {c.media === 'video' ? <Video className="size-4 text-muted" /> : <Phone className="size-4 text-muted" />}
                        {callTitle(c, t('calls.conference'))}
                      </Link>
                      <div className="mt-0.5 text-xs text-muted">
                        {t(`calls.kind.${c.kind}`)} · {c.host?.name ?? '—'} · {t('calls.participantsCount', { count: c.participants.length })}
                      </div>
                    </td>
                    <td className="px-5 py-2.5">
                      <Badge tone={STATUS_TONE[c.status] ?? 'neutral'}>{t(`calls.status.${c.status}`)}</Badge>
                      {c.status === 'active' && <span className="ml-1.5 text-xs text-muted">{t('calls.online', { count: c.online })}</span>}
                    </td>
                    <td className="hidden px-5 py-2.5 tabular-nums text-muted md:table-cell">{formatDateTime(c.scheduled_at ?? c.started_at ?? c.created_at, i18n.language)}</td>
                    <td className="hidden px-5 py-2.5 text-right tabular-nums text-muted sm:table-cell">{durationText(c.duration)}</td>
                  </tr>
                ))}
                {list.data && list.data.items.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-5 py-10 text-center text-muted">
                      {t('common.empty')}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}
      {list.data && list.data.total > SIZE && <Pagination page={page} size={SIZE} total={list.data.total} onPage={setPage} />}
    </div>
  )
}
