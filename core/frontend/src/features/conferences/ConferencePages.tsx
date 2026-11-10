import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarClock, Plus, Trash2, Users, Video } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, send } from '../../lib/api'
import { cn } from '../../lib/cn'
import { formatDateTime } from '../../lib/format'
import { errorText } from '../auth/errorText'
import { RoomView } from '../calls/RoomView'
import type { TokenResp } from '../calls/api'
import { usePositionOptions } from '../org/usePositionOptions'

type Status = 'scheduled' | 'live' | 'ended' | 'cancelled'
interface Conf {
  id: number
  title: string
  description: string | null
  starts_at: string
  duration_min: number
  capacity: number
  audience: { all?: boolean; position_ids?: number[]; branch_ids?: number[]; department_ids?: number[] }
  status: Status
  tasks: { title: string; description?: string | null; due_days: number }[]
  auto_tasks_for_absent: boolean
  recording_url: string | null
  host: { id: number; name: string } | null
  online: number
  attended: number
  report: {
    invited: number
    attended: number
    attendance_pct: number
    avg_minutes: number
    tasks_created: number
    people: { user_id: number; name: string; minutes: number; pct: number; joins: number }[]
    absent: { user_id: number; name: string }[]
  } | null
  can: { manage: boolean; host: boolean }
}
const TONE: Record<Status, 'info' | 'success' | 'neutral' | 'danger'> = { scheduled: 'info', live: 'success', ended: 'neutral', cancelled: 'danger' }
const area = 'w-full rounded-control bg-surface px-3 py-2 text-[13px] shadow-[inset_0_0_0_1px_var(--border-strong)] outline-none focus:ring-2 focus:ring-primary/30'

/** /conferences: onlayn darslar (100 kishigacha) — oflayn darslar o'rniga. */
export function ConferencesPage() {
  const { t, i18n } = useTranslation()
  const [scope, setScope] = useState<'upcoming' | 'past'>('upcoming')
  const q = useQuery({ queryKey: ['conferences', scope], queryFn: () => api<{ items: Conf[]; can_manage: boolean }>(`/api/v1/conferences?scope=${scope}`), refetchInterval: 30_000 })
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <PageHeader
        title={t('conf.title')}
        subtitle={t('conf.subtitle')}
        actions={
          q.data?.can_manage && (
            <Link to="/conferences/new">
              <Button>
                <Plus className="size-4" />
                {t('conf.new')}
              </Button>
            </Link>
          )
        }
      />
      <div className="flex gap-2">
        {(['upcoming', 'past'] as const).map((s) => (
          <button key={s} type="button" onClick={() => setScope(s)} className={cn('rounded-full px-3.5 py-1.5 text-xs font-semibold', scope === s ? 'bg-primary text-primary-fg' : 'border border-border bg-surface hover:bg-surface-2')}>
            {t(`conf.scope.${s}`)}
          </button>
        ))}
      </div>
      {!q.data ? (
        <Skeleton className="h-40" />
      ) : q.data.items.length === 0 ? (
        <Card className="flex flex-col items-center gap-2 p-10 text-center text-sm text-muted">
          <Video className="size-8" />
          {t('conf.empty')}
        </Card>
      ) : (
        q.data.items.map((c) => (
          <Link key={c.id} to={`/conferences/${c.id}`}>
            <Card className="flex flex-wrap items-center gap-3 p-4 transition hover:-translate-y-0.5 hover:shadow-pop">
              <span className={cn('grid size-11 place-items-center rounded-control text-white', c.status === 'live' ? 'bg-emerald-500' : 'bg-primary')}>
                <Video className="size-5" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="font-semibold">{c.title}</div>
                <div className="text-xs text-muted">
                  {formatDateTime(c.starts_at, i18n.language)} · {t('conf.minutes', { n: c.duration_min })} · {c.host?.name ?? '—'}
                </div>
              </div>
              {c.status === 'live' && <Badge tone="success">{t('conf.onlineN', { n: c.online })}</Badge>}
              <Badge tone={TONE[c.status]}>{t(`conf.status.${c.status}`)}</Badge>
            </Card>
          </Link>
        ))
      )}
    </div>
  )
}

/** /conferences/new: yangi onlayn dars (alohida sahifa). */
export function ConferenceFormPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const toast = useToast()
  const qc = useQueryClient()
  const positions = usePositionOptions()
  const branches = useQuery({ queryKey: ['branches', 'select'], queryFn: () => api<{ items: { id: number; name: string; number: number | null }[] }>('/api/v1/branches?size=200'), retry: false })
  const [title, setTitle] = useState('')
  const [desc, setDesc] = useState('')
  const [startsAt, setStartsAt] = useState('')
  const [duration, setDuration] = useState(60)
  const [all, setAll] = useState(false)
  const [posIds, setPosIds] = useState<number[]>([])
  const [brIds, setBrIds] = useState<number[]>([])
  const [tasks, setTasks] = useState<{ title: string; due_days: number }[]>([])
  const [absent, setAbsent] = useState(true)
  const [rec, setRec] = useState('')
  const toggle = (arr: number[], id: number) => (arr.includes(id) ? arr.filter((x) => x !== id) : [...arr, id])
  const save = useMutation({
    mutationFn: () =>
      send<Conf>('POST', '/api/v1/conferences', {
        title, description: desc || null, starts_at: new Date(startsAt).toISOString(), duration_min: duration, capacity: 100,
        audience: { all, position_ids: all ? [] : posIds, branch_ids: all ? [] : brIds, department_ids: [] },
        tasks: tasks.filter((x) => x.title.trim().length >= 2), auto_tasks_for_absent: absent, recording_url: rec || null,
      }), // prettier-ignore
    onSuccess: (c) => {
      void qc.invalidateQueries({ queryKey: ['conferences'] })
      toast.push({ title: t('conf.created'), tone: 'success' })
      navigate(`/conferences/${c.id}`, { replace: true })
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  return (
    <form onSubmit={submit} className="mx-auto flex max-w-3xl flex-col gap-5">
      <PageHeader title={t('conf.new')} backTo="/conferences" backLabel={t('conf.title')} />
      <FormSection title={t('conf.main')}>
        <Field label={t('conf.f.title')}>{(id) => <Input id={id} value={title} onChange={(e) => setTitle(e.target.value)} required minLength={2} maxLength={200} placeholder={t('conf.ph.title')} />}</Field>
        <Field label={t('conf.f.description')}>{(id) => <textarea id={id} rows={3} value={desc} onChange={(e) => setDesc(e.target.value)} maxLength={4000} className={area} />}</Field>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t('conf.f.startsAt')}>{(id) => <Input id={id} type="datetime-local" value={startsAt} onChange={(e) => setStartsAt(e.target.value)} required />}</Field>
          <Field label={t('conf.f.duration')}>{(id) => <Input id={id} type="number" min={10} max={480} value={duration} onChange={(e) => setDuration(Number(e.target.value))} />}</Field>
        </div>
        <Field label={t('conf.f.recording')} hint={t('conf.f.recordingHint')}>{(id) => <Input id={id} value={rec} onChange={(e) => setRec(e.target.value)} placeholder="https://youtu.be/..." />}</Field>
      </FormSection>
      <FormSection title={t('conf.audience')} description={t('conf.audienceHint')}>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={all} onChange={(e) => setAll(e.target.checked)} />
          {t('conf.all')}
        </label>
        {!all && (
          <>
            <div>
              <div className="mb-1 text-xs font-semibold text-muted">{t('conf.byPosition')}</div>
              <div className="flex max-h-48 flex-wrap gap-1.5 overflow-auto">
                {positions.map((p) => (
                  <button key={p.id} type="button" onClick={() => setPosIds(toggle(posIds, p.id))} className={cn('rounded-full border px-2.5 py-1 text-xs', posIds.includes(p.id) ? 'border-primary bg-primary text-primary-fg' : 'border-border hover:bg-surface-2')}>
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
            {(branches.data?.items.length ?? 0) > 0 && (
              <div>
                <div className="mb-1 text-xs font-semibold text-muted">{t('conf.byBranch')}</div>
                <div className="flex max-h-40 flex-wrap gap-1.5 overflow-auto">
                  {branches.data?.items.map((b) => (
                    <button key={b.id} type="button" onClick={() => setBrIds(toggle(brIds, b.id))} className={cn('rounded-full border px-2.5 py-1 text-xs', brIds.includes(b.id) ? 'border-primary bg-primary text-primary-fg' : 'border-border hover:bg-surface-2')}>
                      {b.number ? `№${b.number} ` : ''}
                      {b.name}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </FormSection>
      <FormSection title={t('conf.tasks')} description={t('conf.tasksHint')}>
        {tasks.map((x, i) => (
          <div key={i} className="flex items-end gap-2">
            <div className="flex-1">
              <Field label={t('conf.f.taskTitle')}>{(id) => <Input id={id} value={x.title} onChange={(e) => setTasks(tasks.map((y, j) => (j === i ? { ...y, title: e.target.value } : y)))} maxLength={200} />}</Field>
            </div>
            <Field label={t('conf.f.dueDays')}>{(id) => <Input id={id} type="number" min={0} max={60} value={x.due_days} onChange={(e) => setTasks(tasks.map((y, j) => (j === i ? { ...y, due_days: Number(e.target.value) } : y)))} className="w-24" />}</Field>
            <Button type="button" variant="ghost" aria-label={t('common.delete')} onClick={() => setTasks(tasks.filter((_, j) => j !== i))}>
              <Trash2 className="size-4" />
            </Button>
          </div>
        ))}
        {tasks.length < 10 && (
          <Button type="button" variant="outline" className="self-start" onClick={() => setTasks([...tasks, { title: '', due_days: 3 }])}>
            <Plus className="size-4" />
            {t('conf.addTask')}
          </Button>
        )}
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={absent} onChange={(e) => setAbsent(e.target.checked)} />
          {t('conf.absentTasks')}
        </label>
      </FormSection>
      <FormFooter error={save.isError ? errorText(t, save.error) : null}>
        <Link to="/conferences">
          <Button type="button" variant="outline">
            {t('common.cancel')}
          </Button>
        </Link>
        <Button type="submit" disabled={save.isPending || title.trim().length < 2 || !startsAt}>
          {t('conf.schedule')}
        </Button>
      </FormFooter>
    </form>
  )
}

/** /conferences/:id: dars tafsiloti, qo'shilish, yakunlash va hisobot. */
export function ConferenceDetailPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const toast = useToast()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['conferences', 'one', id], queryFn: () => api<Conf>(`/api/v1/conferences/${id}`), refetchInterval: 20_000 })
  const end = useMutation({
    mutationFn: () => send<Conf>('POST', `/api/v1/conferences/${id}/end`),
    onSuccess: (c) => (qc.setQueryData(['conferences', 'one', id], c), toast.push({ title: t('conf.ended'), tone: 'success' })),
    onError: (e) => toast.push({ title: errorText(t, e), tone: 'danger' }),
  })
  const c = q.data
  if (!c) return <Skeleton className="mx-auto h-72 max-w-4xl" />
  const r = c.report
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader title={c.title} subtitle={`${formatDateTime(c.starts_at, i18n.language)} · ${t('conf.minutes', { n: c.duration_min })}`} backTo="/conferences" backLabel={t('conf.title')} />
      <Card className="flex flex-col gap-3 p-5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={TONE[c.status]}>{t(`conf.status.${c.status}`)}</Badge>
          <Badge>
            <Users className="mr-1 inline size-3" />
            {t('conf.onlineN', { n: c.online })}
          </Badge>
          <Badge>{t('conf.capacity', { n: c.capacity })}</Badge>
          <span className="text-xs text-muted">
            {t('conf.host')}: {c.host?.name ?? '—'}
          </span>
        </div>
        {c.description && <p className="whitespace-pre-wrap text-sm">{c.description}</p>}
        {c.tasks.length > 0 && (
          <div className="text-sm">
            <div className="text-xs font-semibold uppercase tracking-wide text-muted">{t('conf.tasks')}</div>
            <ul className="mt-1 list-disc pl-5">
              {c.tasks.map((x, i) => (
                <li key={i}>
                  {x.title} <span className="text-xs text-muted">({t('conf.dueN', { n: x.due_days })})</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {c.recording_url && (
          <a href={c.recording_url} target="_blank" rel="noreferrer" className="text-sm font-semibold text-primary hover:underline">
            {t('conf.recording')}
          </a>
        )}
        <div className="flex flex-wrap gap-2">
          {(c.status === 'scheduled' || c.status === 'live') && (
            <Link to={`/conferences/${c.id}/room`}>
              <Button>
                <Video className="size-4" />
                {c.can.host && c.status === 'scheduled' ? t('conf.start') : t('conf.join')}
              </Button>
            </Link>
          )}
          {c.can.host && c.status === 'live' && (
            <Button variant="outline" className="text-danger" disabled={end.isPending} onClick={() => end.mutate()}>
              {t('conf.end')}
            </Button>
          )}
        </div>
        {c.status === 'scheduled' && (
          <p className="flex items-center gap-1.5 text-xs text-muted">
            <CalendarClock className="size-3.5" />
            {t('conf.joinHint')}
          </p>
        )}
      </Card>
      {r && (
        <Card className="flex flex-col gap-3 p-5">
          <h3 className="font-semibold">{t('conf.report')}</h3>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
            {(
              [
                [t('conf.r.invited'), r.invited],
                [t('conf.r.attended'), r.attended],
                [t('conf.r.pct'), `${r.attendance_pct}%`],
                [t('conf.r.avg'), t('conf.minutes', { n: r.avg_minutes })],
                [t('conf.r.tasks'), r.tasks_created],
              ] as [string, string | number][]
            ).map(([k, v]) => (
              <div key={k} className="rounded-control bg-surface-2 p-3">
                <div className="text-lg font-bold tabular-nums">{v}</div>
                <div className="text-xs text-muted">{k}</div>
              </div>
            ))}
          </div>
          <table className="w-full text-sm">
            <thead className="text-xs text-muted">
              <tr>
                <th className="py-1 text-left font-medium">{t('conf.r.name')}</th>
                <th className="py-1 text-right font-medium">{t('conf.r.minutes')}</th>
                <th className="py-1 text-right font-medium">%</th>
                <th className="py-1 text-right font-medium">{t('conf.r.joins')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {r.people.map((p) => (
                <tr key={p.user_id}>
                  <td className="py-1.5">{p.name}</td>
                  <td className="py-1.5 text-right tabular-nums">{p.minutes}</td>
                  <td className={cn('py-1.5 text-right tabular-nums', p.pct >= 80 ? 'text-emerald-600' : p.pct >= 40 ? 'text-amber-600' : 'text-rose-600')}>{p.pct}</td>
                  <td className="py-1.5 text-right tabular-nums">{p.joins}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {r.absent.length > 0 && (
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-rose-600">{t('conf.r.absent', { n: r.absent.length })}</div>
              <p className="mt-1 text-sm text-muted">{r.absent.map((x) => x.name).join(', ')}</p>
            </div>
          )}
        </Card>
      )}
    </div>
  )
}

/** /conferences/:id/room: dars xonasi (mikrofon o'chiq kiriladi, ekranda 24 tagacha oyna, qatnashuv har 30 soniyada). */
export function ConferenceRoomPage() {
  const { t } = useTranslation()
  const id = Number(useParams().id)
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [startedAt] = useState(() => Date.now())
  const join = useQuery({ queryKey: ['conferences', 'join', id], queryFn: () => send<{ token: string; url: string | null; room: string; host: boolean; title: string }>('POST', `/api/v1/conferences/${id}/join`), retry: false, staleTime: Infinity, gcTime: 0 })
  useEffect(() => {
    if (!join.data) return
    const h = window.setInterval(() => void send('POST', `/api/v1/conferences/${id}/heartbeat`).catch(() => undefined), 30_000)
    return () => window.clearInterval(h)
  }, [join.data, id])
  const leave = () => {
    void send('POST', `/api/v1/conferences/${id}/heartbeat`).catch(() => undefined)
    navigate(`/conferences/${id}`)
  }
  const end = async () => {
    await send('POST', `/api/v1/conferences/${id}/end`).catch(() => undefined)
    void qc.invalidateQueries({ queryKey: ['conferences'] })
    navigate(`/conferences/${id}`)
  }
  if (join.isError)
    return (
      <Card className="mx-auto max-w-xl p-6 text-center text-sm">
        <p className="text-danger">{errorText(t, join.error)}</p>
        <Link to={`/conferences/${id}`} className="mt-3 inline-block font-semibold text-primary">
          {t('conf.back')}
        </Link>
      </Card>
    )
  if (!join.data) return <Skeleton className="mx-auto h-96 max-w-5xl" />
  const tok: TokenResp = { token: join.data.token, url: join.data.url, room: join.data.room, identity: '', media: join.data.host ? 'video' : 'audio' }
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-3">
      <h1 className="text-lg font-semibold">{join.data.title}</h1>
      <RoomView tok={tok} startedAt={startedAt} canEnd={join.data.host} banner={join.data.host ? t('conf.hostBanner') : t('conf.mutedBanner')} onLeave={leave} onEnd={() => void end()} startMuted={!join.data.host} maxTiles={24} />
    </div>
  )
}
