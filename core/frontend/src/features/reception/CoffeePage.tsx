import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Coffee } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/EmptyState'
import { Field, Input } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { api, send } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { errorText } from '../auth/errorText'

type Order = {
  id: number
  place: string
  items: string
  guests: number
  note: string | null
  status: 'new' | 'accepted' | 'done' | 'cancelled'
  requested_by: string | null
  handled_by: string | null
  mine: boolean
  created_at: string
}
type OrderList = { items: Order[]; can_serve: boolean }

const TONE = { new: 'warning', accepted: 'info', done: 'success', cancelled: 'neutral' } as const
const QUICK = ['tea', 'coffee', 'water', 'sweets'] as const

/** /reception/coffee: Kofe-ledi — choy/kofe buyurtma qilish; kofe-ledi va resepshin hamma buyurtmani ko'radi va yetkazadi. */
export function CoffeePage() {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const [scope, setScope] = useState<'mine' | 'all'>('mine')
  const list = useQuery({ queryKey: ['coffee', scope], queryFn: () => api<OrderList>(`/api/v1/reception/coffee?scope=${scope}`), refetchInterval: 15_000 })
  const canServe = list.data?.can_serve
  const [place, setPlace] = useState('')
  const [items, setItems] = useState('')
  const [guests, setGuests] = useState('1')
  const [note, setNote] = useState('')
  const refresh = () => void qc.invalidateQueries({ queryKey: ['coffee'] })
  const save = useMutation({
    mutationFn: () => send<Order>('POST', '/api/v1/reception/coffee', { place, items, guests: Number(guests) || 1, note: note || null }),
    onSuccess: () => {
      setItems('')
      setNote('')
      refresh()
    },
  })
  const act = useMutation({ mutationFn: ({ id, a }: { id: number; a: string }) => send<Order>('POST', `/api/v1/reception/coffee/${id}/${a}`), onSuccess: refresh })
  const add = (k: string) => setItems((s) => (s ? `${s}, ${t(`coffee.quick.${k}`)}` : t(`coffee.quick.${k}`)))
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  const pill = (on: boolean) => 'rounded-full border px-3 py-1.5 text-xs font-medium ' + (on ? 'border-primary bg-primary text-primary-fg' : 'border-border bg-surface text-muted hover:text-text')

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader title={t('coffee.title')} subtitle={t('coffee.subtitle')} />
      <div className="grid gap-5 lg:grid-cols-[340px_1fr]">
        <Card className="h-fit p-5">
          <form onSubmit={submit} className="flex flex-col gap-3">
            <div className="font-medium">{t('coffee.new')}</div>
            <Field label={t('coffee.place')}>{(id) => <Input id={id} value={place} onChange={(e) => setPlace(e.target.value)} placeholder={t('coffee.placeHint')} maxLength={120} />}</Field>
            <Field label={t('coffee.items')}>{(id) => <Input id={id} value={items} onChange={(e) => setItems(e.target.value)} maxLength={300} />}</Field>
            <div className="flex flex-wrap gap-1.5">
              {QUICK.map((k) => (
                <button key={k} type="button" onClick={() => add(k)} className={pill(false)}>
                  + {t(`coffee.quick.${k}`)}
                </button>
              ))}
            </div>
            <Field label={t('coffee.guests')}>{(id) => <Input id={id} type="number" min={1} max={100} value={guests} onChange={(e) => setGuests(e.target.value)} />}</Field>
            <Field label={t('coffee.note')}>{(id) => <Input id={id} value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} />}</Field>
            {save.isError && <p role="alert" className="text-sm text-danger">{errorText(t, save.error)}</p>}
            <Button type="submit" disabled={save.isPending || place.trim().length < 2 || items.trim().length < 2}>
              <Coffee className="size-4" />
              {t('coffee.send')}
            </Button>
          </form>
        </Card>
        <div className="flex flex-col gap-3">
          {canServe && (
            <div className="flex gap-2">
              {(['mine', 'all'] as const).map((s) => (
                <button key={s} aria-pressed={scope === s} onClick={() => setScope(s)} className={pill(scope === s)}>
                  {t(`coffee.scope.${s}`)}
                </button>
              ))}
            </div>
          )}
          {act.isError && <p role="alert" className="text-sm text-danger">{errorText(t, act.error)}</p>}
          {!list.data ? (
            <Skeleton className="h-40" />
          ) : list.data.items.length === 0 ? (
            <Card>
              <EmptyState icon={Coffee} title={t('coffee.empty')} />
            </Card>
          ) : (
            list.data.items.map((o) => (
              <Card key={o.id} className="flex flex-wrap items-start justify-between gap-3 p-4">
                <div className="min-w-0">
                  <div className="font-medium">
                    {o.place} · {o.items}
                  </div>
                  <div className="text-sm text-muted">
                    {t('coffee.guestsN', { n: o.guests })} · {o.requested_by} · {formatDateTime(o.created_at, i18n.language)}
                    {o.handled_by && ` · ${t('coffee.by')} ${o.handled_by}`}
                  </div>
                  {o.note && <div className="mt-1 text-sm">{o.note}</div>}
                </div>
                <div className="flex flex-wrap items-center gap-1.5">
                  <Badge tone={TONE[o.status]}>{t(`coffee.status.${o.status}`)}</Badge>
                  {canServe && o.status === 'new' && (
                    <Button variant="outline" className="h-8" disabled={act.isPending} onClick={() => act.mutate({ id: o.id, a: 'accept' })}>
                      {t('coffee.accept')}
                    </Button>
                  )}
                  {canServe && (o.status === 'new' || o.status === 'accepted') && (
                    <Button className="h-8" disabled={act.isPending} onClick={() => act.mutate({ id: o.id, a: 'done' })}>
                      {t('coffee.done')}
                    </Button>
                  )}
                  {(o.mine || canServe) && (o.status === 'new' || o.status === 'accepted') && (
                    <Button variant="ghost" className="h-8" disabled={act.isPending} onClick={() => act.mutate({ id: o.id, a: 'cancel' })}>
                      {t('common.cancel')}
                    </Button>
                  )}
                </div>
              </Card>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
