import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { PageHeader } from '../../components/layout/PageHeader'
import { Skeleton } from '../../components/ui/Skeleton'
import { api, send } from '../../lib/api'
import { errorText } from '../auth/errorText'
import { Filters } from './Filters'
import { defaultFilter, filterQuery, type TaskFilter } from './filterState'
import { TaskCard } from './TaskCard'
import { ViewTabs } from './ViewTabs'
import { STATUSES, type Board, type TaskItem, type TStatus } from './api'

const HEAD: Record<TStatus, string> = { todo: 'border-t-muted', in_progress: 'border-t-info', review: 'border-t-warning', done: 'border-t-success' }

/** /tasks/board: kanban. Kartani sudrab ustunlar orasida yoki ustun ichida ko'chirish (tartib saqlanadi). */
export function BoardPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [filter, setFilter] = useState<TaskFilter>(defaultFilter)
  const [dragId, setDragId] = useState<number | null>(null)
  const dragRef = useRef<number | null>(null) // drop hodisasida eskirgan holatdan saqlaydi
  const [overCol, setOverCol] = useState<TStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const params = new URLSearchParams()
  filterQuery(filter, params)
  const key = ['tasks', 'board', params.toString()]
  const board = useQuery({ queryKey: key, queryFn: () => api<Board>(`/api/v1/tasks/board?${params}`), refetchInterval: 30_000 })

  const move = useMutation({
    mutationFn: ({ id, status, before }: { id: number; status: TStatus; before: number | null }) => send<TaskItem>('POST', `/api/v1/tasks/${id}/move`, { status, before_id: before }),
    onMutate: async ({ id, status, before }) => {
      setError(null)
      await qc.cancelQueries({ queryKey: key })
      const prev = qc.getQueryData<Board>(key)
      if (prev) {
        // Optimistik yangilash: karta yangi ustunda, `before` dan oldin
        const next = structuredClone(prev)
        let card: TaskItem | undefined
        for (const s of STATUSES) {
          const i = next[s].tasks.findIndex((x) => x.id === id)
          if (i >= 0) {
            card = next[s].tasks.splice(i, 1)[0]
            next[s].total -= 1
          }
        }
        if (card) {
          card.status = status
          const idx = before ? next[status].tasks.findIndex((x) => x.id === before) : -1
          next[status].tasks.splice(idx >= 0 ? idx : next[status].tasks.length, 0, card)
          next[status].total += 1
          qc.setQueryData(key, next)
        }
      }
      return { prev }
    },
    onError: (e, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(key, ctx.prev)
      setError(errorText(t, e))
    },
    onSettled: () => void qc.invalidateQueries({ queryKey: ['tasks'] }),
  })

  const drop = (status: TStatus, before: number | null) => {
    const id = dragRef.current
    if (id !== null && id !== before) move.mutate({ id, status, before })
    dragRef.current = null
    setDragId(null)
    setOverCol(null)
  }

  return (
    <div className="mx-auto flex max-w-[1500px] flex-col gap-4">
      <PageHeader title={t('tasks.title')} subtitle={t('tasks.subtitle')} actions={<ViewTabs />} />
      <div className="flex flex-wrap items-center gap-3 rounded-card bg-surface p-3 shadow-card">
        <Filters value={filter} onChange={setFilter} />
      </div>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      {!board.data ? (
        <Skeleton className="h-96" />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {STATUSES.map((s) => (
            <section
              key={s}
              aria-label={t(`tasks.status.${s}`)}
              onDragOver={(e) => (e.preventDefault(), setOverCol(s))}
              onDragLeave={() => setOverCol((c) => (c === s ? null : c))}
              onDrop={(e) => (e.preventDefault(), drop(s, null))}
              className={`flex min-h-48 flex-col gap-3 rounded-card border-t-4 bg-surface-2 p-3 ${HEAD[s]} ${overCol === s ? 'ring-2 ring-primary/40' : ''}`}
            >
              <h2 className="flex items-center justify-between px-1 text-sm font-semibold">
                {t(`tasks.status.${s}`)}
                <span className="rounded-full bg-surface px-2 py-0.5 text-xs tabular-nums text-muted">{board.data[s].total}</span>
              </h2>
              {board.data[s].tasks.map((task) => (
                <div key={task.id} onDragOver={(e) => (e.preventDefault(), e.stopPropagation(), setOverCol(s))} onDrop={(e) => (e.preventDefault(), e.stopPropagation(), drop(s, task.id))}>
                  <TaskCard task={task} dragging={dragId === task.id} canMove={!task.archived} onDragStart={() => ((dragRef.current = task.id), setDragId(task.id))} onDragEnd={() => ((dragRef.current = null), setDragId(null), setOverCol(null))} onMove={(st) => move.mutate({ id: task.id, status: st, before: null })} />
                </div>
              ))}
              {board.data[s].tasks.length === 0 && <p className="px-1 py-6 text-center text-xs text-muted">{t('tasks.emptyColumn')}</p>}
              {s === 'done' && <p className="px-1 text-center text-[11px] text-muted">{t('tasks.doneWindow')}</p>}
            </section>
          ))}
        </div>
      )}
    </div>
  )
}
