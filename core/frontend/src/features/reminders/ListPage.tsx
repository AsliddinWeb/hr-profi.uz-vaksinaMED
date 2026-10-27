import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BellRing, Pause, Play, Plus } from 'lucide-react'
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
import { api, send } from '../../lib/api'
import { errorText } from '../auth/errorText'
import { dayText, timeText, whenText, type ReminderPage, type UpcomingItem } from './api'
import { repeatText } from './repeatText'

const SIZE = 30

/** /reminders: eslatmalar ro'yxati va yaqin 7 kunlik jadval. */
export function ListPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [scope, setScope] = useState<'mine' | 'shared'>('mine')
  const [state, setState] = useState('active')
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const params = new URLSearchParams({ scope, state, page: String(page), size: String(SIZE) })
  if (q.trim()) params.set('q', q.trim())
  const list = useQuery({ queryKey: ['reminders', 'list', params.toString()], queryFn: () => api<ReminderPage>(`/api/v1/reminders?${params}`), placeholderData: (p) => p, refetchInterval: 60_000 })
  const agenda = useQuery({ queryKey: ['reminders', 'upcoming'], queryFn: () => api<UpcomingItem[]>('/api/v1/reminders/upcoming?days=7'), refetchInterval: 60_000 })
  const toggle = useMutation({
    mutationFn: ({ id, active }: { id: number; active: boolean }) => send('POST', `/api/v1/reminders/${id}/${active ? 'pause' : 'resume'}`),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['reminders'] }),
  })

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader
        title={t('reminders.title')}
        subtitle={t('reminders.subtitle')}
        actions={
          <Link to="/reminders/new">
            <Button>
              <Plus className="size-4" />
              {t('reminders.new')}
            </Button>
          </Link>
        }
      />
      {agenda.data && agenda.data.length > 0 && (
        <Card tint="lilac" className="p-5">
          <h2 className="flex items-center gap-2 font-semibold">
            <BellRing className="size-4" />
            {t('reminders.agenda')}
          </h2>
          <ul className="mt-3 grid gap-x-8 gap-y-1.5 text-sm sm:grid-cols-2">
            {agenda.data.slice(0, 8).map((a, i) => (
              <li key={`${a.reminder_id}-${i}`} className="flex items-baseline justify-between gap-3">
                <Link to={`/reminders/${a.reminder_id}`} className="truncate hover:underline">
                  {a.title}
                </Link>
                <span className="shrink-0 tabular-nums text-muted">
                  {dayText(a.at)} {timeText(a.at)}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
      <Card className="flex flex-wrap items-center gap-3 p-4">
        <div className="flex rounded-control bg-(--seg-bg) p-0.5 text-[13px]">
          {(['mine', 'shared'] as const).map((s) => (
            <button key={s} onClick={() => (setScope(s), setPage(1))} aria-pressed={scope === s} className={scope === s ? 'rounded-lg bg-(--seg-on) px-3 py-1.5 font-medium text-text shadow-card' : 'rounded-lg px-3 py-1.5 text-muted transition-colors hover:text-text'}>
              {t(`reminders.scope.${s}`)}
            </button>
          ))}
        </div>
        <Input className="min-w-40 flex-1" placeholder={t('reminders.search')} value={q} onChange={(e) => (setQ(e.target.value), setPage(1))} aria-label={t('reminders.search')} />
        <Select className="w-auto" value={state} onChange={(e) => (setState(e.target.value), setPage(1))} aria-label={t('attendance.statusLabel')}>
          {['active', 'paused', 'finished', 'all'].map((s) => (
            <option key={s} value={s}>
              {t(`reminders.state.${s}`)}
            </option>
          ))}
        </Select>
      </Card>
      {toggle.isError && <p role="alert" className="text-sm text-danger">{errorText(t, toggle.error)}</p>}
      {list.isLoading ? (
        <Skeleton className="h-40" />
      ) : (
        <Card className="overflow-hidden">
          <ul className="divide-y divide-border">
            {list.data?.items.map((r) => (
              <li key={r.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
                <div className="min-w-0">
                  <Link to={`/reminders/${r.id}`} className="font-medium hover:text-primary hover:underline">
                    {r.title}
                  </Link>
                  <div className="mt-0.5 text-xs text-muted">{repeatText(t, r)}</div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="text-right text-sm tabular-nums">
                    {r.finished ? <Badge>{t('reminders.finished')}</Badge> : !r.is_active ? <Badge tone="warning">{t('reminders.paused')}</Badge> : whenText(r.snooze_at ?? r.next_at)}
                    {r.snooze_at && <div className="text-xs text-muted">{t('reminders.snoozed')}</div>}
                  </div>
                  {scope === 'mine' && !r.finished && (
                    <Button variant="ghost" className="h-9 px-2" aria-label={r.is_active ? t('reminders.pause') : t('reminders.resume')} onClick={() => toggle.mutate({ id: r.id, active: r.is_active })}>
                      {r.is_active ? <Pause className="size-4" /> : <Play className="size-4" />}
                    </Button>
                  )}
                </div>
              </li>
            ))}
            {list.data?.items.length === 0 && <li className="px-5 py-10 text-center text-muted">{t('reminders.empty')}</li>}
          </ul>
        </Card>
      )}
      {list.data && list.data.total > SIZE && <Pagination page={page} size={SIZE} total={list.data.total} onPage={setPage} />}
    </div>
  )
}
