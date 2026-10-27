import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlarmClock, Check, ExternalLink, Pause, Pencil, Play, Trash2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { whenText, type ReminderDetail } from './api'
import { repeatText } from './repeatText'

/** /reminders/:id: eslatma tafsiloti, kechiktirish, bajarildi, to'xtatish va tarix. */
export function DetailPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const q = useQuery({ queryKey: ['reminders', 'one', id], queryFn: () => api<ReminderDetail>(`/api/v1/reminders/${id}`), retry: false, refetchInterval: 30_000 })
  const refresh = () => void qc.invalidateQueries({ queryKey: ['reminders'] })
  const act = useMutation({ mutationFn: ({ path, body }: { path: string; body?: unknown }) => send('POST', `/api/v1/reminders/${id}/${path}`, body), onSuccess: refresh })
  const del = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/reminders/${id}`),
    onSuccess: () => {
      refresh()
      toast.push({ title: t('reminders.deleted'), tone: 'success' })
      navigate('/reminders')
    },
  })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const r = q.data
  if (!r) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  const canAct = r.is_active || r.snooze_at !== null

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <PageHeader
        title={r.title}
        subtitle={repeatText(t, r)}
        backTo="/reminders"
        backLabel={t('reminders.title')}
        actions={
          r.is_owner && (
            <>
              <Link to={`/reminders/${id}/edit`}>
                <Button variant="outline">
                  <Pencil className="size-4" />
                  {t('common.edit')}
                </Button>
              </Link>
              <Button
                variant="outline"
                className="text-danger"
                disabled={del.isPending}
                onClick={async () => {
                  if (await confirm({ title: t('reminders.delete'), body: t('org.deleteConfirm', { name: r.title }), danger: true, confirmLabel: t('common.delete') })) del.mutate()
                }}
              >
                <Trash2 className="size-4" />
                {t('reminders.delete')}
              </Button>
            </>
          )
        }
      />
      <Card className="flex flex-col gap-4 p-6">
        <div className="flex flex-wrap items-center gap-2">
          {r.finished ? <Badge>{t('reminders.finished')}</Badge> : r.is_active ? <Badge tone="success">{t('reminders.state.active')}</Badge> : <Badge tone="warning">{t('reminders.paused')}</Badge>}
          {r.snooze_at && <Badge tone="warning">{t('reminders.snoozedUntil', { time: whenText(r.snooze_at) })}</Badge>}
          <Badge>{r.telegram ? t('reminders.viaTelegram') : t('reminders.appOnly')}</Badge>
        </div>
        {r.note && <p className="whitespace-pre-wrap text-sm">{r.note}</p>}
        <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
          <Item label={t('reminders.nextAt')} value={whenText(r.snooze_at ?? r.next_at)} />
          <Item label={t('reminders.lastFired')} value={whenText(r.last_fired_at)} />
          <Item label={t('reminders.fireCount')} value={String(r.fire_count)} />
          {r.recipients.length > 0 && <Item label={t('reminders.form.recipients')} value={r.recipients.map((p) => p.name).join(', ')} />}
        </dl>
        {r.link && (
          <Link to={r.link} className="inline-flex w-fit items-center gap-1.5 text-sm text-primary hover:underline">
            <ExternalLink className="size-4" />
            {t('reminders.openLink')}
          </Link>
        )}
        {canAct && (
          <div className="flex flex-wrap gap-2 border-t border-border pt-4">
            <Button variant="outline" disabled={act.isPending} onClick={() => act.mutate({ path: 'snooze', body: { minutes: 10 } })}>
              <AlarmClock className="size-4" />
              {t('reminders.snooze.m10')}
            </Button>
            <Button variant="outline" disabled={act.isPending} onClick={() => act.mutate({ path: 'snooze', body: { minutes: 60 } })}>
              {t('reminders.snooze.h1')}
            </Button>
            <Button variant="outline" disabled={act.isPending} onClick={() => act.mutate({ path: 'snooze', body: { tomorrow: true } })}>
              {t('reminders.snooze.tomorrow')}
            </Button>
            <Button disabled={act.isPending} onClick={() => act.mutate({ path: 'ack' })}>
              <Check className="size-4" />
              {t('reminders.ack')}
            </Button>
          </div>
        )}
        {r.is_owner && !r.finished && (
          <div>
            <Button variant="ghost" disabled={act.isPending} onClick={() => act.mutate({ path: r.is_active ? 'pause' : 'resume' })}>
              {r.is_active ? <Pause className="size-4" /> : <Play className="size-4" />}
              {r.is_active ? t('reminders.pause') : t('reminders.resume')}
            </Button>
          </div>
        )}
        {act.isError && <p role="alert" className="text-sm text-danger">{errorText(t, act.error)}</p>}
      </Card>

      {r.next_five.length > 0 && (
        <Card className="p-6">
          <h2 className="font-semibold">{t('reminders.nextFive')}</h2>
          <ul className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm tabular-nums">
            {r.next_five.map((n) => (
              <li key={n}>{whenText(n)}</li>
            ))}
          </ul>
        </Card>
      )}

      <Card className="p-6">
        <h2 className="font-semibold">{t('answers.history')}</h2>
        <ol className="mt-4 flex flex-col gap-3 border-l border-border pl-5">
          {r.events.map((e) => (
            <li key={e.id} className="relative flex flex-wrap items-baseline justify-between gap-2 text-sm">
              <span className="absolute -left-[26px] top-1.5 size-2.5 rounded-full bg-primary" aria-hidden />
              <span className="font-medium">{t(`reminders.event.${e.action}`)}</span>
              <span className="text-xs text-muted">{formatDateTime(e.created_at, i18n.language)}</span>
            </li>
          ))}
        </ol>
      </Card>
    </div>
  )
}

function Item({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="tabular-nums">{value}</dd>
    </div>
  )
}
