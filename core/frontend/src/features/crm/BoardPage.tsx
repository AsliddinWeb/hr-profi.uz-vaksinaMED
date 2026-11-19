import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Search } from 'lucide-react'
import { motion } from 'motion/react'
import { useRef, useState, type DragEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { api, send } from '../../lib/api'
import { cn } from '../../lib/cn'
import { errorText } from '../auth/errorText'
import { shortMoney, type Board, type DealCard } from './api'
import { ActivityChip, Stars } from './parts'

/** /crm: savdo voronkasi. Kartani sudrab bosqichlar orasida ko'chirish; bosqichga kirganda ehtimollik va keyingi faoliyat avtomatik qo'yiladi. */
export function CrmBoardPage() {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [owner, setOwner] = useState('')
  const [q, setQ] = useState('')
  const [overCol, setOverCol] = useState<number | null>(null)
  const [dragId, setDragId] = useState<number | null>(null)
  const dragRef = useRef<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const params = new URLSearchParams()
  if (owner) params.set('owner', owner)
  if (q.trim()) params.set('q', q.trim())
  const key = ['crm', 'board', params.toString()]
  const board = useQuery({ queryKey: key, queryFn: () => api<Board>(`/api/v1/crm/board?${params}`), refetchInterval: 30_000 })

  const move = useMutation({
    mutationFn: ({ id, stage, before }: { id: number; stage: number; before: number | null }) => send('POST', `/api/v1/crm/deals/${id}/move`, { stage_id: stage, before_id: before }),
    onMutate: async ({ id, stage, before }) => {
      setError(null)
      await qc.cancelQueries({ queryKey: key })
      const prev = qc.getQueryData<Board>(key)
      if (prev) {
        const next = structuredClone(prev)
        let card: DealCard | undefined
        for (const col of next.stages) {
          const i = col.deals.findIndex((d) => d.id === id)
          if (i >= 0) {
            card = col.deals.splice(i, 1)[0]
            col.count -= 1
            col.total -= card.amount
          }
        }
        const target = next.stages.find((c) => c.id === stage)
        if (card && target) {
          card.stage_id = stage
          card.probability = target.probability
          const idx = before ? target.deals.findIndex((d) => d.id === before) : -1
          target.deals.splice(idx >= 0 ? idx : target.deals.length, 0, card)
          target.count += 1
          target.total += card.amount
          qc.setQueryData(key, next)
        }
      }
      return { prev }
    },
    onError: (e, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(key, ctx.prev)
      setError(errorText(t, e))
    },
    onSettled: () => void qc.invalidateQueries({ queryKey: ['crm'] }),
  })

  const drop = (stage: number, before: number | null) => {
    const id = dragRef.current
    if (id !== null && id !== before) move.mutate({ id, stage, before })
    dragRef.current = null
    setDragId(null)
    setOverCol(null)
  }

  const data = board.data
  const total = data?.stages.reduce((s, c) => s + (c.is_won ? 0 : c.total), 0) ?? 0

  return (
    <div className="mx-auto flex max-w-[1700px] flex-col gap-4">
      <PageHeader
        title={t('crm.title')}
        subtitle={data ? t('crm.subtitle', { total: shortMoney(total, i18n.language) }) : undefined}
        actions={
          data?.can_create && (
            <Link to="/crm/new">
              <Button>
                <Plus className="size-4" />
                {t('crm.newDeal')}
              </Button>
            </Link>
          )
        }
      />
      <div className="flex flex-wrap items-center gap-3 rounded-card bg-surface p-3 shadow-card">
        <div className="relative min-w-56 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('crm.search')} aria-label={t('crm.search')} className="pl-9" />
        </div>
        {data?.sees_all && (
          <Select value={owner} onChange={(e) => setOwner(e.target.value)} aria-label={t('crm.field.owner')} className="max-w-56">
            <option value="">{t('crm.filter.all')}</option>
            <option value="mine">{t('crm.filter.mine')}</option>
          </Select>
        )}
      </div>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      {!data ? (
        <Skeleton className="h-96" />
      ) : (
        <div className="flex gap-4 overflow-x-auto pb-3">
          {data.stages.map((col) => (
            <section
              key={col.id}
              aria-label={col.name}
              onDragOver={(e) => (e.preventDefault(), setOverCol(col.id))}
              onDragLeave={() => setOverCol((c) => (c === col.id ? null : c))}
              onDrop={(e) => (e.preventDefault(), drop(col.id, null))}
              className={cn('flex w-72 shrink-0 flex-col gap-2.5 rounded-card bg-surface-2 p-3', overCol === col.id && 'ring-2 ring-primary/40')}
            >
              <header className="px-1">
                <div className="flex items-center justify-between gap-2">
                  <h2 className="truncate text-sm font-semibold">{col.name}</h2>
                  <span className="text-xs font-semibold tabular-nums">{shortMoney(col.total, i18n.language)} UZS</span>
                </div>
                <div className="mt-1 flex items-center justify-between text-[11px] text-muted">
                  <span>
                    {t('crm.deals', { n: col.count })} · {col.probability}%
                  </span>
                  {col.overdue > 0 && <span className="font-medium text-danger">{t('crm.overdueN', { n: col.overdue })}</span>}
                </div>
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-3">
                  <motion.div
                    className="h-full rounded-full"
                    style={{ background: col.is_won ? 'linear-gradient(90deg, var(--success), var(--accent))' : 'linear-gradient(90deg, var(--primary), var(--c-violet))' }}
                    initial={{ width: 0 }}
                    animate={{ width: `${col.probability}%` }}
                    transition={{ duration: 0.8, ease: [0.22, 0.8, 0.24, 1] }}
                  />
                </div>
              </header>
              {col.deals.map((d, i) => (
                <motion.article
                  key={d.id}
                  layout
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: dragId === d.id ? 0.4 : 1, y: 0 }}
                  transition={{ layout: { type: 'spring', stiffness: 420, damping: 34 }, delay: Math.min(i, 8) * 0.03 }}
                  draggable={data.can_create}
                  onDragStartCapture={(e: DragEvent) => (e.dataTransfer.setData('text/plain', String(d.id)), (e.dataTransfer.effectAllowed = 'move'), (dragRef.current = d.id), setDragId(d.id))}
                  onDragEndCapture={() => ((dragRef.current = null), setDragId(null), setOverCol(null))}
                  onDragOverCapture={(e: DragEvent) => (e.preventDefault(), e.stopPropagation(), setOverCol(col.id))}
                  onDropCapture={(e: DragEvent) => (e.preventDefault(), e.stopPropagation(), drop(col.id, d.id))}
                  onClick={() => navigate(`/crm/deals/${d.id}`)}
                  whileHover={{ y: -2, boxShadow: 'var(--shadow-hover)' }}
                  className="relative cursor-pointer overflow-hidden rounded-control border border-border bg-surface p-3 shadow-card"
                >
                  <span aria-hidden className="absolute inset-y-0 left-0 w-[3px]" style={{ background: d.priority >= 3 ? 'var(--c-rose)' : d.priority === 2 ? 'var(--c-amber)' : d.priority === 1 ? 'var(--c-blue)' : 'var(--border)' }} />
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="line-clamp-2 text-[13px] font-medium">{d.title}</h3>
                    <Stars value={d.priority} />
                  </div>
                  {(d.company || d.contact_name) && <p className="mt-0.5 truncate text-xs text-muted">{d.contact_name || d.company}</p>}
                  {d.tags.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {d.tags.map((tag) => (
                        <span key={tag} className="rounded-full bg-info/12 px-2 py-0.5 text-[10px] font-medium text-info">
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                  <div className="mt-2 flex items-center justify-between gap-2 text-xs">
                    <span className="font-semibold tabular-nums">{shortMoney(d.amount, i18n.language)}</span>
                    <span className="text-muted tabular-nums">{d.probability}%</span>
                  </div>
                  <div className="mt-2 flex items-center justify-between gap-2">
                    <span className="truncate text-[11px] text-muted" title={d.next_activity?.title}>
                      {d.owner?.name ?? '—'}
                    </span>
                    <ActivityChip a={d.next_activity} />
                  </div>
                </motion.article>
              ))}
              {col.deals.length === 0 && <p className="px-1 py-6 text-center text-xs text-muted">{t('crm.emptyColumn')}</p>}
            </section>
          ))}
        </div>
      )}
    </div>
  )
}
