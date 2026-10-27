import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'

interface Complaint {
  id: number
  category: string
  title: string
  text: string
  status: 'new' | 'in_progress' | 'resolved' | 'rejected'
  is_anonymous: boolean
  created_at: string
  author: string | null
  assignee: string | null
  response: string | null
  history: { action: string; actor: string | null; text: string | null; at: string }[]
  own: boolean
  can_handle: boolean
}
const CATS = ['salary', 'manager', 'schedule', 'conditions', 'colleague', 'system', 'other'] as const
const TONE = { new: 'warning', in_progress: 'warning', resolved: 'success', rejected: 'danger' } as const
const area = 'w-full rounded-control border border-border bg-surface px-3 py-2 text-sm'

/** /complaints: o'z murojaatlarim va (HR uchun) kelgan shikoyatlar. */
export function ComplaintsPage() {
  const { t, i18n } = useTranslation()
  const can = useCan()
  const manage = can('complaints.manage')
  const [scope, setScope] = useState<'mine' | 'inbox'>(manage ? 'inbox' : 'mine')
  const list = useQuery({ queryKey: ['complaints', scope], queryFn: () => api<Complaint[]>(`/api/v1/complaints?scope=${scope}`), refetchInterval: 60_000 })
  const pill = (on: boolean) => 'rounded-full border px-3 py-1.5 text-xs font-medium ' + (on ? 'border-primary bg-primary text-primary-fg' : 'border-border bg-surface text-muted hover:text-text')
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title={t('complaints.title')}
        subtitle={t('complaints.subtitle')}
        actions={
          <Link to="/complaints/new">
            <Button>
              <Plus className="size-4" />
              {t('complaints.new')}
            </Button>
          </Link>
        }
      />
      {manage && (
        <div className="flex gap-2">
          {(['inbox', 'mine'] as const).map((s) => (
            <button key={s} aria-pressed={scope === s} onClick={() => setScope(s)} className={pill(scope === s)}>
              {t(`complaints.scope.${s}`)}
            </button>
          ))}
        </div>
      )}
      {!list.data ? (
        <Skeleton className="h-40" />
      ) : (
        <div className="flex flex-col gap-3">
          {list.data.map((c) => (
            <Link key={c.id} to={`/complaints/${c.id}`}>
              <Card className="flex flex-wrap items-center justify-between gap-3 p-4 hover:bg-surface-2">
                <div className="min-w-0">
                  <div className="font-medium">{c.title}</div>
                  <div className="text-sm text-muted">
                    {t(`complaints.cat.${c.category}`)} · {formatDateTime(c.created_at, i18n.language)}
                    {c.author ? ` · ${c.author}` : c.is_anonymous ? ` · ${t('complaints.anonymous')}` : ''}
                  </div>
                </div>
                <Badge tone={TONE[c.status]}>{t(`complaints.status.${c.status}`)}</Badge>
              </Card>
            </Link>
          ))}
          {list.data.length === 0 && <Card className="p-8 text-center text-muted">{t('common.empty')}</Card>}
        </div>
      )}
    </div>
  )
}

/** /complaints/new */
export function ComplaintFormPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [category, setCategory] = useState('other')
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [anon, setAnon] = useState(false)
  const save = useMutation({
    mutationFn: () => send<Complaint>('POST', '/api/v1/complaints', { category, title, text, is_anonymous: anon }),
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['complaints'] })
      toast.push({ title: t('complaints.sent'), tone: 'success' })
      navigate(`/complaints/${r.id}`, { replace: true })
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={t('complaints.new')} subtitle={t('complaints.formHint')} backTo="/complaints" backLabel={t('complaints.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('complaints.what')}>
          <Field label={t('complaints.category')}>
            {(id) => (
              <Select id={id} value={category} onChange={(e) => setCategory(e.target.value)}>
                {CATS.map((c) => (
                  <option key={c} value={c}>
                    {t(`complaints.cat.${c}`)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label={t('complaints.topic')}>{(id) => <Input id={id} value={title} onChange={(e) => setTitle(e.target.value)} required minLength={3} maxLength={200} />}</Field>
          <Field label={t('complaints.text')}>{(id) => <textarea id={id} value={text} onChange={(e) => setText(e.target.value)} rows={6} maxLength={5000} className={area} />}</Field>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" className="mt-0.5 size-4" checked={anon} onChange={(e) => setAnon(e.target.checked)} />
            <span>
              {t('complaints.anonymous')}
              <span className="block text-xs text-muted">{t('complaints.anonymousHint')}</span>
            </span>
          </label>
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate('/complaints')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || title.trim().length < 3 || text.trim().length < 5}>
            {t('complaints.send')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}

/** /complaints/:id */
export function ComplaintDetailPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['complaints', 'one', id], queryFn: () => api<Complaint>(`/api/v1/complaints/${id}`), retry: false })
  const [resp, setResp] = useState('')
  const act = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: unknown }) => send('POST', `/api/v1/complaints/${id}/${path}`, body ?? {}),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['complaints'] }),
  })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const c = q.data
  if (!c) return <Skeleton className="mx-auto h-72 max-w-3xl" />
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <PageHeader title={c.title} subtitle={t(`complaints.cat.${c.category}`)} backTo="/complaints" backLabel={t('complaints.title')} actions={<Badge tone={TONE[c.status]}>{t(`complaints.status.${c.status}`)}</Badge>} />
      <Card className="flex flex-col gap-2 p-5 text-sm">
        <p className="whitespace-pre-wrap">{c.text}</p>
        <p className="text-xs text-muted">
          {c.author ?? (c.is_anonymous ? t('complaints.anonymous') : '—')} · {formatDateTime(c.created_at, i18n.language)}
          {c.assignee && ` · ${t('complaints.assignee')}: ${c.assignee}`}
        </p>
        {c.response && (
          <p className="rounded-control bg-surface-2 p-3">
            <span className="text-xs text-muted">{t('complaints.response')}:</span> {c.response}
          </p>
        )}
      </Card>
      {c.can_handle && (
        <Card className="flex flex-col gap-3 p-5">
          <h2 className="font-semibold">{t('complaints.handle')}</h2>
          {c.status === 'new' && (
            <div>
              <Button variant="outline" disabled={act.isPending} onClick={() => act.mutate({ path: 'take' })}>
                {t('complaints.take')}
              </Button>
            </div>
          )}
          <textarea value={resp} onChange={(e) => setResp(e.target.value)} rows={3} maxLength={3000} placeholder={t('complaints.responsePlaceholder')} aria-label={t('complaints.response')} className={area} />
          <div className="flex gap-2">
            <Button disabled={act.isPending || resp.trim().length < 3} onClick={() => act.mutate({ path: 'answer', body: { action: 'resolve', response: resp } })}>
              {t('complaints.resolve')}
            </Button>
            <Button variant="outline" className="text-danger" disabled={act.isPending || resp.trim().length < 3} onClick={() => act.mutate({ path: 'answer', body: { action: 'reject', response: resp } })}>
              {t('complaints.reject')}
            </Button>
          </div>
          {act.isError && <p role="alert" className="text-sm text-danger">{errorText(t, act.error)}</p>}
        </Card>
      )}
      <Card className="p-5">
        <h2 className="font-semibold">{t('answers.history')}</h2>
        <ol className="mt-3 flex flex-col gap-3 border-l border-border pl-5">
          {c.history.map((h, i) => (
            <li key={i} className="relative text-sm">
              <span className="absolute -left-[26px] top-1.5 size-2.5 rounded-full bg-primary" aria-hidden />
              <div className="flex flex-wrap justify-between gap-2">
                <span className="font-medium">{t(`complaints.event.${h.action}`)}</span>
                <span className="text-xs text-muted">{formatDateTime(h.at, i18n.language)}</span>
              </div>
              {h.actor && <div className="text-xs text-muted">{h.actor}</div>}
              {h.text && <p className="mt-1 text-muted">{h.text}</p>}
            </li>
          ))}
        </ol>
      </Card>
    </div>
  )
}
