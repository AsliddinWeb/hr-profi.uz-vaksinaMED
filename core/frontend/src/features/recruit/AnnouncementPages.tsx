import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Sparkles, X } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/EmptyState'
import { Field, Input } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { Tabs } from '../../components/ui/Tabs'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'

type Ch = { channel: string; targets: string[] }
type AStatus = 'draft' | 'approved' | 'cancelled'
type Ann = {
  id: number
  title: string
  text: string
  channels: Ch[]
  status: AStatus
  ai_review: { score: number | null; issues: string[]; improved: string } | null
  vacancy_id: number | null
  request: { id: number; number: string; count: number } | null
  recruiter: string | null
  created_by: string | null
  approved_by: string | null
  approved_at: string | null
  created_at: string
  channel_options: string[]
}
const TONE = { draft: 'warning', approved: 'success', cancelled: 'neutral' } as const
// nom kiritiladigan joylar (Telegram kanallari, saytlar, Instagram sahifalari...)
const WITH_TARGETS = new Set(['telegram', 'instagram', 'site', 'other', 'target'])
const area = 'w-full rounded-control border border-border bg-surface px-3 py-2 text-sm'

/** /recruit/announcements — tasdiqlangan zayavkalardan tayyorlangan e'lonlar. */
export function AnnouncementsPage() {
  const { t, i18n } = useTranslation()
  const [st, setSt] = useState<AStatus>('draft')
  const q = useQuery({ queryKey: ['recruit', 'announcements', st], queryFn: () => api<{ items: (Pick<Ann, 'id' | 'title' | 'status' | 'channels' | 'vacancy_id' | 'created_at'>)[]; counts: Record<AStatus, number> }>(`/api/v1/recruit/announcements?status=${st}`) })
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader title={t('ann.title')} subtitle={t('ann.subtitle')} />
      <Tabs items={(['draft', 'approved', 'cancelled'] as const).map((k) => ({ key: k, label: t(`ann.st.${k}`), count: q.data?.counts[k] ?? 0 }))} value={st} onChange={setSt} />
      {!q.data ? (
        <Skeleton className="h-40" />
      ) : q.data.items.length === 0 ? (
        <Card>
          <EmptyState icon={Sparkles} title={t('ann.empty')} />
        </Card>
      ) : (
        <div className="flex flex-col gap-3">
          {q.data.items.map((a) => (
            <Link key={a.id} to={`/recruit/announcements/${a.id}`}>
              <Card className="flex flex-wrap items-center justify-between gap-3 p-4 hover:bg-surface-2">
                <div>
                  <div className="font-medium">{a.title}</div>
                  <div className="text-xs text-muted">
                    {formatDate(a.created_at, i18n.language)} · {a.channels.map((c) => t(`ann.ch.${c.channel}`)).join(', ') || '—'}
                  </div>
                </div>
                <Badge tone={TONE[a.status]}>{t(`ann.st.${a.status}`)}</Badge>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

/** /recruit/announcements/:id — e'lon matni, AI tekshiruvi, joylar va tasdiq (tasdiqdan keyin vakansiya ochiladi). */
export function AnnouncementDetailPage() {
  const { t } = useTranslation()
  const id = Number(useParams().id)
  const qc = useQueryClient()
  const navigate = useNavigate()
  const toast = useToast()
  const can = useCan()
  const edit = can('recruit.manage') || can('recruit.approve')
  const q = useQuery({ queryKey: ['recruit', 'announcement', id], queryFn: () => api<Ann>(`/api/v1/recruit/announcements/${id}`), retry: false })
  const [form, setForm] = useState<{ title: string; text: string; channels: Ch[] } | null>(null)
  const [review, setReview] = useState<Ann['ai_review']>(null)
  const [newTarget, setNewTarget] = useState<Record<string, string>>({})
  const a = q.data
  const f = form ?? (a ? { title: a.title, text: a.text, channels: a.channels } : null)
  const fail = (e: unknown) => toast.push({ title: errorText(t, e), tone: 'danger' })
  const save = useMutation({ mutationFn: () => send<Ann>('PUT', `/api/v1/recruit/announcements/${id}`, f), onSuccess: (r) => (qc.setQueryData(['recruit', 'announcement', id], r), setForm(null), toast.push({ title: t('common.saved'), tone: 'success' })), onError: fail })
  const ai = useMutation({ mutationFn: () => send<NonNullable<Ann['ai_review']>>('POST', `/api/v1/recruit/announcements/${id}/ai-review`, f), onSuccess: setReview, onError: fail })
  const approve = useMutation({
    mutationFn: async () => {
      await send('PUT', `/api/v1/recruit/announcements/${id}`, f)
      return send<Ann>('POST', `/api/v1/recruit/announcements/${id}/approve`)
    },
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['recruit'] })
      toast.push({ title: t('ann.approved'), tone: 'success' })
      if (r.vacancy_id) navigate(`/recruit/vacancies/${r.vacancy_id}`)
    },
    onError: fail,
  })
  const cancel = useMutation({ mutationFn: () => send('POST', `/api/v1/recruit/announcements/${id}/cancel`), onSuccess: () => (void qc.invalidateQueries({ queryKey: ['recruit'] }), navigate('/recruit/announcements')), onError: fail })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!a || !f) return <Skeleton className="mx-auto h-96 max-w-5xl" />
  const ro = !edit || a.status !== 'draft'
  const set = (patch: Partial<typeof f>) => setForm({ ...f, ...patch })
  const chOn = (c: string) => f.channels.some((x) => x.channel === c)
  const toggle = (c: string) => set({ channels: chOn(c) ? f.channels.filter((x) => x.channel !== c) : [...f.channels, { channel: c, targets: [] }] })
  const addTarget = (c: string) => {
    const v = (newTarget[c] ?? '').trim()
    if (!v) return
    set({ channels: f.channels.map((x) => (x.channel === c && !x.targets.includes(v) ? { ...x, targets: [...x.targets, v] } : x)) })
    setNewTarget({ ...newTarget, [c]: '' })
  }
  const rev = review ?? a.ai_review
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <PageHeader
        title={a.title}
        subtitle={a.request ? `${t('ann.fromRequest')} ${a.request.number} · ${t('rreq.count')}: ${a.request.count}` : undefined}
        backTo="/recruit/announcements"
        backLabel={t('ann.title')}
        actions={<Badge tone={TONE[a.status]}>{t(`ann.st.${a.status}`)}</Badge>}
      />
      {a.vacancy_id && (
        <Card className="flex items-center justify-between gap-3 border-success/40 p-4 text-sm">
          {t('ann.vacancyOpened')}
          <Link to={`/recruit/vacancies/${a.vacancy_id}`} className="font-medium text-primary hover:underline">
            {t('ann.openVacancy')}
          </Link>
        </Card>
      )}
      <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
        <Card className="flex flex-col gap-4 p-5">
          <Field label={t('ann.titleField')}>{(fid) => <Input id={fid} value={f.title} disabled={ro} onChange={(e) => set({ title: e.target.value })} maxLength={200} />}</Field>
          <Field label={t('ann.text')} hint={t('ann.textHint')}>
            {(fid) => <textarea id={fid} rows={18} value={f.text} disabled={ro} onChange={(e) => set({ text: e.target.value })} maxLength={8000} className={area} />}
          </Field>
          {!ro && (
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" disabled={ai.isPending} onClick={() => ai.mutate()}>
                <Sparkles className="size-4" />
                {ai.isPending ? t('comp.ai.thinking') : t('ann.aiCheck')}
              </Button>
              <span className="flex-1" />
              <Button variant="outline" disabled={save.isPending} onClick={() => save.mutate()}>
                {t('comp.wiz.saveDraft')}
              </Button>
            </div>
          )}
          {rev && (
            <div className="flex flex-col gap-2 rounded-lg border border-primary/30 bg-primary/5 p-4 text-sm">
              <div className="flex items-center gap-2 font-medium">
                <Sparkles className="size-4 text-primary" />
                {t('ann.aiResult')}
                {rev.score != null && <Badge tone={rev.score >= 80 ? 'success' : rev.score >= 50 ? 'warning' : 'danger'}>{rev.score}/100</Badge>}
              </div>
              {rev.issues.map((x, i) => (
                <div key={i}>• {x}</div>
              ))}
              {rev.improved && !ro && (
                <div className="flex flex-col gap-2">
                  <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-surface p-3 font-sans text-sm">{rev.improved}</pre>
                  <Button className="w-fit" onClick={() => set({ text: rev.improved })}>
                    <Check className="size-4" />
                    {t('ann.applyImproved')}
                  </Button>
                </div>
              )}
            </div>
          )}
        </Card>
        <div className="flex h-fit flex-col gap-4 lg:sticky lg:top-4">
          <Card className="flex flex-col gap-3 p-5">
            <div className="font-semibold">{t('ann.whereTitle')}</div>
            <div className="text-xs text-muted">{t('ann.whereHint')}</div>
            {a.channel_options.map((c) => (
              <div key={c} className="flex flex-col gap-2 rounded-lg border border-border p-3">
                <label className="flex items-center gap-2 text-sm font-medium">
                  <input type="checkbox" checked={chOn(c)} disabled={ro} onChange={() => toggle(c)} />
                  {t(`ann.ch.${c}`)}
                </label>
                {chOn(c) && WITH_TARGETS.has(c) && (
                  <>
                    <div className="flex flex-wrap gap-1">
                      {f.channels
                        .find((x) => x.channel === c)
                        ?.targets.map((x) => (
                          <span key={x} className="inline-flex items-center gap-1 rounded-full bg-surface-2 px-2 py-0.5 text-xs">
                            {x}
                            {!ro && (
                              <button type="button" aria-label={t('common.delete')} onClick={() => set({ channels: f.channels.map((y) => (y.channel === c ? { ...y, targets: y.targets.filter((z) => z !== x) } : y)) })}>
                                <X className="size-3" />
                              </button>
                            )}
                          </span>
                        ))}
                    </div>
                    {!ro && (
                      <div className="flex gap-1">
                        <Input className="h-8" value={newTarget[c] ?? ''} placeholder={t(`ann.ph.${c}`)} onChange={(e) => setNewTarget({ ...newTarget, [c]: e.target.value })} onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addTarget(c))} aria-label={t(`ann.ch.${c}`)} />
                        <Button variant="outline" className="h-8" onClick={() => addTarget(c)}>
                          +
                        </Button>
                      </div>
                    )}
                  </>
                )}
              </div>
            ))}
          </Card>
          {!ro && (
            <Card className="flex flex-col gap-2 p-5">
              <div className="text-sm text-muted">{t('ann.approveHint')}</div>
              <Button disabled={approve.isPending || f.channels.length === 0} onClick={() => approve.mutate()}>
                <Check className="size-4" />
                {t('ann.approve')}
              </Button>
              <Button variant="ghost" className="text-danger" disabled={cancel.isPending} onClick={() => cancel.mutate()}>
                {t('ann.cancel')}
              </Button>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
