import { useQueryClient } from '@tanstack/react-query'
import { Minus, Plus, Trash2, Trophy } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { UserPicker, type PickedUser } from '../../components/UserPicker'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { useToast } from '../../components/ui/toastContext'
import { send } from '../../lib/api'
import { cn } from '../../lib/cn'
import { errorText } from '../auth/errorText'
import { toneOf, type OverviewRow } from '../company/StrategyExtras'

const BASE = '/api/v1/org/goals'

/** Bo'limlar reytingi: bajarilish % bo'yicha avtomatik saralanadi */
export function DeptRanking({ rows, year }: { rows: OverviewRow[]; year: number }) {
  const { t } = useTranslation()
  const ranked = rows.filter((r) => r.progress !== null).sort((a, b) => (b.progress ?? 0) - (a.progress ?? 0))
  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex items-start gap-3">
        <span className="grid size-9 shrink-0 place-items-center rounded-control bg-primary/10 text-primary">
          <Trophy className="size-[18px]" />
        </span>
        <div>
          <h3 className="font-semibold">{t('stratx.ranking.title')}</h3>
          <p className="text-sm text-muted">{t('stratx.ranking.hint')}</p>
        </div>
      </div>
      {ranked.length === 0 ? (
        <p className="text-sm text-muted">{t('stratx.ranking.noData')}</p>
      ) : (
        <ol className="flex flex-col gap-2">
          {ranked.map((r, i) => (
            <li key={r.id} className={cn('grid grid-cols-[2rem_minmax(0,1fr)_minmax(6rem,14rem)_3rem] items-center gap-3 rounded-control px-2 py-1.5 text-sm', i === 0 && 'bg-success/10')}>
              <span className={cn('grid size-7 place-items-center rounded-full text-xs font-semibold', i === 0 ? 'bg-success text-white' : 'bg-surface-2 text-muted')}>{i + 1}</span>
              <span className="flex min-w-0 items-center gap-2">
                <Link to={`/org/goals/${r.id}?year=${year}`} className="truncate font-medium hover:underline">
                  {r.name}
                </Link>
                {i === 0 && <Badge tone="success">{t('stratx.ranking.leader')}</Badge>}
              </span>
              <div className="h-2 overflow-hidden rounded-full bg-surface-2">
                <div className={cn('h-full rounded-full', toneOf(r.progress))} style={{ width: `${Math.min(r.progress ?? 0, 100)}%` }} />
              </div>
              <span className="text-right font-semibold tabular-nums">{r.progress}%</span>
            </li>
          ))}
        </ol>
      )}
    </Card>
  )
}

export type Task = { id: number; goal_id: number; title: string; owner_user_id: number | null; owner: string | null; due_date: string | null; progress: number; note: string | null; sort_order: number }

/** Maqsad ostidagi haftalik vazifalar: +/− bilan progress, qo'shish va o'chirish */
export function GoalTasks({ goalId, tasks, canEdit }: { goalId: number; tasks: Task[]; canEdit: boolean }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const [title, setTitle] = useState('')
  const [due, setDue] = useState('')
  const [owner, setOwner] = useState<PickedUser | null>(null)
  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true)
    try {
      await fn()
      await qc.invalidateQueries({ queryKey: ['goals'] })
    } catch (e) {
      toast.push({ title: errorText(t, e), tone: 'danger' })
    } finally {
      setBusy(false)
    }
  }
  const step = (task: Task, delta: number) => run(() => send('PUT', `${BASE}/tasks/${task.id}/progress`, { progress: Math.max(0, Math.min(100, task.progress + delta)) }))
  return (
    <div className="flex flex-col gap-2 border-t border-border pt-3">
      <div>
        <div className="text-sm font-medium">{t('stratx.tasks.title')}</div>
        <div className="text-xs text-muted">{t('stratx.tasks.hint')}</div>
      </div>
      {tasks.length === 0 && <p className="text-xs text-muted">{t('stratx.tasks.empty')}</p>}
      <ul className="flex flex-col gap-1.5">
        {tasks.map((task) => (
          <li key={task.id} className="grid items-center gap-2 rounded-control bg-surface-2/60 px-3 py-2 text-sm sm:grid-cols-[minmax(0,1fr)_minmax(6rem,10rem)_auto]">
            <span className="min-w-0">
              <span className="block truncate">{task.title}</span>
              <span className="block text-xs text-muted">{[task.owner, task.due_date && new Date(task.due_date).toLocaleDateString()].filter(Boolean).join(' · ')}</span>
            </span>
            <div className="flex items-center gap-2">
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface">
                <div className={cn('h-full rounded-full', toneOf(task.progress))} style={{ width: `${task.progress}%` }} />
              </div>
              <span className="w-9 text-right text-xs tabular-nums">{task.progress}%</span>
            </div>
            {canEdit && (
              <span className="flex gap-1">
                <Button variant="outline" className="size-7 p-0" aria-label={t('stratx.tasks.dec')} title={t('stratx.tasks.dec')} disabled={busy || task.progress <= 0} onClick={() => void step(task, -10)}>
                  <Minus className="size-3.5" />
                </Button>
                <Button variant="outline" className="size-7 p-0" aria-label={t('stratx.tasks.inc')} title={t('stratx.tasks.inc')} disabled={busy || task.progress >= 100} onClick={() => void step(task, 10)}>
                  <Plus className="size-3.5" />
                </Button>
                <Button variant="ghost" className="size-7 p-0 text-danger" aria-label={t('stratx.tasks.delete')} title={t('stratx.tasks.delete')} disabled={busy} onClick={() => void run(() => send('DELETE', `${BASE}/tasks/${task.id}`))}>
                  <Trash2 className="size-3.5" />
                </Button>
              </span>
            )}
          </li>
        ))}
      </ul>
      {canEdit && (
        <form
          className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_9.5rem_12rem_auto]"
          onSubmit={(e) => {
            e.preventDefault()
            if (!title.trim()) return
            void run(async () => {
              await send('POST', `${BASE}/items/${goalId}/tasks`, { title: title.trim(), due_date: due || null, owner_user_id: owner?.id ?? null, progress: 0, sort_order: tasks.length })
              setTitle('')
              setDue('')
              setOwner(null)
            })
          }}
        >
          <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder={t('stratx.tasks.titlePh')} aria-label={t('stratx.tasks.titlePh')} maxLength={200} />
          <Input type="date" value={due} onChange={(e) => setDue(e.target.value)} aria-label={t('stratx.tasks.due')} title={t('stratx.tasks.due')} />
          <UserPicker value={owner} onChange={setOwner} />
          <Button type="submit" variant="outline" disabled={busy || !title.trim()}>
            <Plus className="size-4" />
            {t('stratx.tasks.add')}
          </Button>
        </form>
      )}
    </div>
  )
}
