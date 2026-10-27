import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Pencil, UtensilsCrossed } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams, useSearchParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api, ApiError, send } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import { StarsInput, StarsView } from './Stars'
import { avgText, type Menu } from './api'

const area = 'w-full rounded-control border border-border bg-surface px-3 py-2 text-sm'

/** /canteen (bugungi menyu), /canteen/rate?t= (QR) va /canteen/menus/:id: menyu va baholash. */
export function MenuPage({ mode }: { mode: 'today' | 'qr' | 'id' }) {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const [sp] = useSearchParams()
  const token = sp.get('t')
  const manage = useCan()('canteen.manage')
  const q = useQuery({
    queryKey: ['canteen', 'page', mode, id, token],
    queryFn: async () => {
      if (mode === 'id') return api<Menu>(`/api/v1/canteen/menus/${id}`)
      if (mode === 'qr') return (await api<{ menu: Menu | null }>(`/api/v1/canteen/qr/resolve?t=${encodeURIComponent(token ?? '')}`)).menu
      return api<Menu | null>('/api/v1/canteen/menus/today')
    },
    retry: false,
  })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (q.isError) {
    return (
      <div className="mx-auto max-w-xl py-16 text-center">
        <p role="alert" className="text-danger">
          {errorText(t, q.error)}
        </p>
      </div>
    )
  }
  if (q.isLoading) return <Skeleton className="mx-auto h-96 max-w-2xl" />
  const m = q.data
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-5">
      <PageHeader
        title={m ? `${t('canteen.menu')} · ${formatDate(m.menu_date, i18n.language)}` : t('canteen.title')}
        subtitle={m?.note ?? t('canteen.subtitle')}
        backTo={mode === 'id' ? '/canteen/menus' : undefined}
        backLabel={t('canteen.menus.title')}
        actions={
          manage &&
          m && (
            <Link to={`/canteen/menus/${m.id}/edit`}>
              <Button variant="outline">
                <Pencil className="size-4" />
                {t('common.edit')}
              </Button>
            </Link>
          )
        }
      />
      {!m ? (
        <Card className="flex flex-col items-center gap-3 p-10 text-center text-muted">
          <UtensilsCrossed className="size-8" />
          {t('canteen.noMenuToday')}
          {manage && (
            <Link to="/canteen/menus/new">
              <Button>{t('canteen.menus.add')}</Button>
            </Link>
          )}
        </Card>
      ) : (
        <Rate key={m.id} m={m} qr={mode === 'qr' ? token : null} />
      )}
    </div>
  )
}

function Rate({ m, qr }: { m: Menu; qr: string | null }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const mine = m.mine
  const [overall, setOverall] = useState<number | null>(mine?.overall?.stars ?? null)
  const [comment, setComment] = useState(mine?.overall?.comment ?? '')
  const [anonymous, setAnonymous] = useState(mine?.overall?.anonymous ?? false)
  const [dishes, setDishes] = useState<Record<number, number | null>>(() => Object.fromEntries(m.dishes.map((d) => [d.id, mine?.dishes[String(d.id)]?.stars ?? null])))
  const [saved, setSaved] = useState(false)
  const canRate = !!m.can_rate && (!m.require_qr || !!qr)
  const save = useMutation({
    mutationFn: () => {
      const changed = m.dishes.filter((d) => (dishes[d.id] ?? null) !== (mine?.dishes[String(d.id)]?.stars ?? null)).map((d) => ({ dish_id: d.id, stars: dishes[d.id] }))
      return send('POST', `/api/v1/canteen/menus/${m.id}/rate`, { overall: overall ? { stars: overall, comment: comment || null, anonymous } : null, dishes: changed, qr })
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['canteen'] })
      setSaved(true)
    },
  })
  const retract = useMutation({ mutationFn: () => send('DELETE', `/api/v1/canteen/menus/${m.id}/rate`), onSuccess: () => void qc.invalidateQueries({ queryKey: ['canteen'] }) })

  return (
    <>
      {m.rating && (
        <Card tint="mint" className="flex items-center justify-between gap-4 p-5">
          <div>
            <div className="text-xs text-muted">{t('canteen.avgRating')}</div>
            <div className="text-2xl font-semibold tabular-nums">{avgText(m.rating.avg)}</div>
          </div>
          <div className="text-right text-sm text-muted">
            <StarsView value={m.rating.avg} />
            <div>{t('canteen.ratingsN', { count: m.rating.count })}</div>
          </div>
        </Card>
      )}
      <Card className="divide-y divide-border p-0">
        {m.dishes.map((d) => (
          <div key={d.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-medium">{d.name}</span>
                <Badge>{t(`canteen.kind.${d.kind}`)}</Badge>
              </div>
              {d.description && <p className="text-xs text-muted">{d.description}</p>}
              {m.rating && d.avg !== null && (
                <p className="text-xs text-muted tabular-nums">
                  {avgText(d.avg)} · {d.count}
                </p>
              )}
            </div>
            {canRate && <StarsInput value={dishes[d.id] ?? null} onChange={(v) => (setDishes({ ...dishes, [d.id]: v }), setSaved(false))} label={d.name} size="size-6" />}
          </div>
        ))}
      </Card>
      {m.can_rate && !canRate && <p className="rounded-control bg-warning/15 p-3 text-sm text-warning">{t('canteen.qrRequired')}</p>}
      {!m.can_rate && <p className="text-center text-sm text-muted">{t('canteen.ratingClosed')}</p>}
      {canRate && (
        <Card className="flex flex-col gap-4 p-5">
          <h2 className="font-semibold">{t('canteen.overall')}</h2>
          <StarsInput value={overall} onChange={(v) => (setOverall(v), setSaved(false))} label={t('canteen.overall')} />
          <textarea value={comment} onChange={(e) => (setComment(e.target.value), setSaved(false))} rows={3} maxLength={2000} placeholder={t('canteen.commentHint')} aria-label={t('canteen.comment')} className={area} />
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4" checked={anonymous} onChange={(e) => (setAnonymous(e.target.checked), setSaved(false))} />
            {t('canteen.anonymous')}
          </label>
          {mine?.overall?.reply && (
            <div className="rounded-control bg-surface-2 p-3 text-sm">
              <div className="mb-1 text-xs font-medium text-muted">{t('canteen.reply')}</div>
              {mine.overall.reply}
            </div>
          )}
          <div className="flex flex-wrap items-center gap-3">
            <Button disabled={save.isPending || (!overall && Object.values(dishes).every((v) => v === null))} onClick={() => save.mutate()}>
              {mine?.overall || Object.keys(mine?.dishes ?? {}).length ? t('canteen.update') : t('canteen.send')}
            </Button>
            {(mine?.overall || Object.keys(mine?.dishes ?? {}).length > 0) && (
              <Button variant="ghost" className="text-danger" disabled={retract.isPending} onClick={() => retract.mutate()}>
                {t('canteen.retract')}
              </Button>
            )}
            {saved && <span className="text-sm text-success">{t('canteen.thanks')}</span>}
          </div>
          {(save.isError || retract.isError) && (
            <p role="alert" className="text-sm text-danger">
              {errorText(t, save.error ?? retract.error)}
            </p>
          )}
        </Card>
      )}
    </>
  )
}
