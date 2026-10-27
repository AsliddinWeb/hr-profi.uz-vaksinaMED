import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input, Select } from '../../components/ui/Input'
import { Pagination } from '../../components/ui/Pagination'
import { Skeleton } from '../../components/ui/Skeleton'
import { api, send } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { addDays, todayLocal } from '../attendance/api'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import { StarsView } from './Stars'
import type { Page, RatingRow } from './api'

const SIZE = 20

/** /canteen/comments: izohlar va past baholar; boshqaruvchi javob yozadi. */
export function CommentsPage() {
  const { t, i18n } = useTranslation()
  const manage = useCan()('canteen.manage')
  const today = todayLocal()
  const [range, setRange] = useState({ start: addDays(today, -29), end: today })
  const [max, setMax] = useState('')
  const [unanswered, setUnanswered] = useState(false)
  const [page, setPage] = useState(1)
  const params = new URLSearchParams({ ...range, page: String(page), size: String(SIZE) })
  if (max) params.set('max_stars', max)
  if (unanswered) params.set('unanswered', 'true')
  const q = useQuery({ queryKey: ['canteen', 'ratings', params.toString()], queryFn: () => api<Page<RatingRow>>(`/api/v1/canteen/ratings?${params}`), placeholderData: (p) => p })
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4">
      <PageHeader title={t('canteen.comments.title')} subtitle={t('canteen.comments.subtitle')} />
      <div className="flex flex-wrap items-center gap-3 rounded-card bg-surface p-3 shadow-card">
        <Input type="date" className="w-40" value={range.start} max={range.end} onChange={(e) => e.target.value && (setRange({ ...range, start: e.target.value }), setPage(1))} aria-label={t('schedule.apply.from')} />
        <span className="text-muted">–</span>
        <Input type="date" className="w-40" value={range.end} min={range.start} onChange={(e) => e.target.value && (setRange({ ...range, end: e.target.value }), setPage(1))} aria-label={t('schedule.apply.to')} />
        <Select className="w-auto" value={max} onChange={(e) => (setMax(e.target.value), setPage(1))} aria-label={t('canteen.comments.stars')}>
          <option value="">{t('canteen.comments.allStars')}</option>
          {[2, 3, 4].map((n) => (
            <option key={n} value={n}>
              ≤ {n} ★
            </option>
          ))}
        </Select>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" className="size-4" checked={unanswered} onChange={(e) => (setUnanswered(e.target.checked), setPage(1))} />
          {t('canteen.comments.unanswered')}
        </label>
      </div>
      {!q.data ? (
        <Skeleton className="h-48" />
      ) : (
        <div className="flex flex-col gap-3">
          {q.data.items.map((r) => (
            <Item key={r.id} r={r} manage={manage} lang={i18n.language} />
          ))}
          {q.data.items.length === 0 && <p className="py-10 text-center text-muted">{t('common.empty')}</p>}
        </div>
      )}
      {q.data && q.data.total > SIZE && <Pagination page={page} size={SIZE} total={q.data.total} onPage={setPage} />}
    </div>
  )
}

function Item({ r, manage, lang }: { r: RatingRow; manage: boolean; lang: string }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [text, setText] = useState('')
  const reply = useMutation({
    mutationFn: () => send('POST', `/api/v1/canteen/ratings/${r.id}/reply`, { reply: text }),
    onSuccess: () => (setText(''), void qc.invalidateQueries({ queryKey: ['canteen'] })),
  })
  return (
    <Card className="flex flex-col gap-2 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <StarsView value={r.stars} />
          <span className="text-sm text-muted tabular-nums">{formatDate(r.menu_date, lang)}</span>
          {r.anonymous && <Badge>{t('canteen.anonymousBadge')}</Badge>}
          {r.via_qr && <Badge tone="success">QR</Badge>}
        </div>
        <span className="text-sm font-medium">{r.employee ?? t('canteen.anonymousName')}</span>
      </div>
      {r.comment && <p className="whitespace-pre-wrap text-sm">{r.comment}</p>}
      {r.reply ? (
        <div className="rounded-control bg-surface-2 p-3 text-sm">
          <div className="mb-1 text-xs font-medium text-muted">{t('canteen.reply')}</div>
          {r.reply}
        </div>
      ) : (
        manage && (
          <div className="flex gap-2">
            <Input value={text} onChange={(e) => setText(e.target.value)} maxLength={2000} placeholder={t('canteen.comments.replyHint')} aria-label={t('canteen.reply')} />
            <Button variant="outline" disabled={!text.trim() || reply.isPending} onClick={() => reply.mutate()}>
              {t('canteen.comments.send')}
            </Button>
          </div>
        )
      )}
      {reply.isError && (
        <p role="alert" className="text-sm text-danger">
          {errorText(t, reply.error)}
        </p>
      )}
    </Card>
  )
}
