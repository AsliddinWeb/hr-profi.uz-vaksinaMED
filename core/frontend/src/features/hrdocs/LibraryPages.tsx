import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BookOpen, Check, FileDown, Paperclip, Plus, Search, Trash2 } from 'lucide-react'
import { useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send, upload } from '../../lib/api'
import { formatDate, formatDateTime } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import { CATEGORIES, type Category, type HrDoc } from './api'

const area = 'w-full rounded-control border border-border bg-surface px-3 py-2 text-sm'
const LIST = '/hr/library'

/** /hr/library: HR hujjatlar kutubxonasi (kategoriyalar bo'yicha). */
export function LibraryPage() {
  const { t } = useTranslation()
  const can = useCan()
  const manage = can('hrdocs.manage')
  const [q, setQ] = useState('')
  const [cat, setCat] = useState<'all' | Category>('all')
  const list = useQuery({ queryKey: ['hrdocs', 'list', q], queryFn: () => api<{ items: HrDoc[]; pending_ack: number }>(`/api/v1/hrdocs${q.trim() ? `?q=${encodeURIComponent(q.trim())}` : ''}`), placeholderData: (p) => p })
  const items = (list.data?.items ?? []).filter((d) => cat === 'all' || d.category === cat)
  const pill = (on: boolean) => 'rounded-full border px-3 py-1.5 text-xs font-medium ' + (on ? 'border-primary bg-primary text-primary-fg' : 'border-border bg-surface text-muted hover:text-text')
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader
        title={t('hrdocs.title')}
        subtitle={t('hrdocs.subtitle')}
        actions={
          manage && (
            <Link to={`${LIST}/new`}>
              <Button>
                <Plus className="size-4" />
                {t('hrdocs.add')}
              </Button>
            </Link>
          )
        }
      />
      {!!list.data?.pending_ack && (
        <Card className="border-warning/40 bg-warning/5 p-4 text-sm">
          <b>{t('hrdocs.pendingBanner', { n: list.data.pending_ack })}</b>
        </Card>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-56 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
          <Input className="pl-9" placeholder={t('hrdocs.search')} value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div className="flex flex-wrap gap-2">
          <button className={pill(cat === 'all')} aria-pressed={cat === 'all'} onClick={() => setCat('all')}>
            {t('hrdocs.all')}
          </button>
          {CATEGORIES.map((c) => (
            <button key={c} className={pill(cat === c)} aria-pressed={cat === c} onClick={() => setCat(c)}>
              {t(`hrdocs.cat.${c}`)}
            </button>
          ))}
        </div>
      </div>
      {!list.data ? (
        <Skeleton className="h-48" />
      ) : (
        CATEGORIES.filter((c) => items.some((d) => d.category === c)).map((c) => (
          <section key={c} className="flex flex-col gap-2">
            <h2 className="text-sm font-semibold text-muted">{t(`hrdocs.cat.${c}`)}</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              {items.filter((d) => d.category === c).map((d) => (
                <Link key={d.id} to={`${LIST}/${d.id}`}>
                  <Card className="flex h-full flex-col gap-2 p-4 hover:bg-surface-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="font-medium">{d.title}</div>
                      {d.needs_ack && <Badge tone="warning">{t('hrdocs.needsAck')}</Badge>}
                      {!d.needs_ack && d.ack && d.requires_ack && <Check className="size-4 text-success" />}
                    </div>
                    <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
                      {d.status === 'draft' ? <Badge>{d.has_body || d.has_file ? t('hrdocs.draft') : t('hrdocs.empty')}</Badge> : <span>v{d.version}</span>}
                      {d.has_file && <Paperclip className="size-3.5" />}
                      {manage && d.requires_ack && d.status === 'published' && <span>{t('hrdocs.acked', { n: d.ack_count ?? 0 })}</span>}
                    </div>
                  </Card>
                </Link>
              ))}
            </div>
          </section>
        ))
      )}
      {list.data && items.length === 0 && <Card className="p-8 text-center text-muted">{t('hrdocs.noDocs')}</Card>}
    </div>
  )
}

/** /hr/library/:id: hujjatni o'qish, «tanishdim», (HR) e'lon qilish, kim tanishgani va versiyalar. */
export function DocViewPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const qc = useQueryClient()
  const can = useCan()
  const manage = can('hrdocs.manage')
  const [note, setNote] = useState('')
  const q = useQuery({ queryKey: ['hrdocs', 'one', id], queryFn: () => api<HrDoc>(`/api/v1/hrdocs/${id}`), retry: false })
  const acks = useQuery({ queryKey: ['hrdocs', 'acks', id], queryFn: () => api<{ version: number; total: number; done: { user: { name: string }; at: string }[]; pending: { user: { name: string } }[] }>(`/api/v1/hrdocs/${id}/acks`), enabled: manage && !!q.data && q.data.status === 'published', retry: false })
  const versions = useQuery({ queryKey: ['hrdocs', 'versions', id], queryFn: () => api<{ version: number; note: string | null; created_at: string; file_name: string | null }[]>(`/api/v1/hrdocs/${id}/versions`), enabled: manage && !!q.data, retry: false })
  const act = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: unknown }) => send<HrDoc>('POST', `/api/v1/hrdocs/${id}/${path}`, body),
    onSuccess: () => {
      setNote('')
      void qc.invalidateQueries({ queryKey: ['hrdocs'] })
    },
  })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!q.data) return <Skeleton className="mx-auto h-64 max-w-3xl" />
  const d = q.data
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <PageHeader
        title={d.title}
        subtitle={`${t(`hrdocs.cat.${d.category}`)}${d.version ? ` · v${d.version}` : ''}${d.published_at ? ` · ${formatDate(d.published_at, i18n.language)}` : ''}`}
        backTo={LIST}
        backLabel={t('hrdocs.title')}
        actions={
          <div className="flex gap-2">
            {d.has_file && (
              <a href={`/api/v1/hrdocs/${d.id}/file`} download>
                <Button variant="outline">
                  <FileDown className="size-4" />
                  {d.file_name ?? t('hrdocs.file')}
                </Button>
              </a>
            )}
            {manage && (
              <Link to={`${LIST}/${d.id}/edit`}>
                <Button variant="outline">{t('common.edit')}</Button>
              </Link>
            )}
          </div>
        }
      />
      <Card className="p-6">
        {d.summary && <p className="mb-3 text-sm text-muted">{d.summary}</p>}
        {d.body?.trim() ? <div className="whitespace-pre-wrap text-sm leading-relaxed">{d.body}</div> : <p className="text-sm text-muted">{t(d.has_file ? 'hrdocs.fileOnly' : 'hrdocs.noContent')}</p>}
      </Card>
      {act.isError && (
        <p role="alert" className="text-sm text-danger">
          {errorText(t, act.error)}
        </p>
      )}
      {d.status === 'published' && d.requires_ack && (
        <Card className="flex flex-wrap items-center justify-between gap-3 p-5">
          {d.needs_ack ? (
            <>
              <span className="text-sm">{t('hrdocs.ackPrompt')}</span>
              <Button disabled={act.isPending} onClick={() => act.mutate({ path: 'ack' })}>
                <Check className="size-4" />
                {t('hrdocs.ackButton')}
              </Button>
            </>
          ) : (
            <span className="text-sm text-success">{t('hrdocs.ackedAt', { when: d.ack ? formatDateTime(d.ack.at, i18n.language) : '', v: d.ack?.version })}</span>
          )}
        </Card>
      )}
      {manage && (
        <Card className="flex flex-col gap-3 p-5">
          <h2 className="font-semibold">{t('hrdocs.publishing')}</h2>
          <p className="text-sm text-muted">{t(d.status === 'published' ? 'hrdocs.publishedHint' : 'hrdocs.draftHint')}</p>
          <Field label={t('hrdocs.versionNote')}>{(fid) => <Input id={fid} value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} />}</Field>
          <div className="flex gap-2">
            <Button disabled={act.isPending} onClick={() => act.mutate({ path: 'publish', body: { note: note || null } })}>
              {t(d.version ? 'hrdocs.publishNew' : 'hrdocs.publish')}
            </Button>
            {d.status === 'published' && (
              <Button variant="outline" disabled={act.isPending} onClick={() => act.mutate({ path: 'unpublish' })}>
                {t('hrdocs.unpublish')}
              </Button>
            )}
          </div>
          {versions.data && versions.data.length > 0 && (
            <ul className="mt-2 flex flex-col gap-1 text-sm">
              {versions.data.map((v) => (
                <li key={v.version} className="text-muted">
                  v{v.version} · {formatDateTime(v.created_at, i18n.language)}
                  {v.note ? ` · ${v.note}` : ''}
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
      {manage && acks.data && d.requires_ack && (
        <Card className="flex flex-col gap-3 p-5">
          <h2 className="font-semibold">{t('hrdocs.ackStatus', { done: acks.data.done.length, total: acks.data.total })}</h2>
          {acks.data.pending.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-muted">{t('hrdocs.notAcked')}</div>
              <p className="text-sm">{acks.data.pending.map((p) => p.user.name).join(', ')}</p>
            </div>
          )}
          {acks.data.done.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-muted">{t('hrdocs.ackedList')}</div>
              <p className="text-sm text-muted">{acks.data.done.map((p) => p.user.name).join(', ')}</p>
            </div>
          )}
        </Card>
      )}
    </div>
  )
}

/** /hr/library/new va /hr/library/:id/edit */
export function DocFormPage() {
  const { id } = useParams()
  const did = id ? Number(id) : null
  const q = useQuery({ queryKey: ['hrdocs', 'one', did], queryFn: () => api<HrDoc>(`/api/v1/hrdocs/${did}`), enabled: did !== null, retry: false })
  if (did === null) return <DocForm doc={null} />
  if (q.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  return q.data ? <DocForm key={q.data.id} doc={q.data} /> : null
}

function DocForm({ doc }: { doc: HrDoc | null }) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const fileRef = useRef<HTMLInputElement>(null)
  const roles = useQuery({ queryKey: ['hrdocs', 'roles'], queryFn: () => api<{ key: string; name_uz: string; name_ru: string }[]>('/api/v1/hrdocs/roles') })
  const [category, setCategory] = useState<Category>(doc?.category ?? 'policy')
  const [title, setTitle] = useState(doc?.title ?? '')
  const [summary, setSummary] = useState(doc?.summary ?? '')
  const [body, setBody] = useState(doc?.body ?? '')
  const [ack, setAck] = useState(doc?.requires_ack ?? false)
  const [picked, setPicked] = useState<string[]>(doc?.roles ?? [])
  const [error, setError] = useState<string | null>(null)
  const save = useMutation({
    mutationFn: () => {
      const payload = { category, title, summary: summary || null, body: body || null, requires_ack: ack, roles: picked, sort_order: 0 }
      return doc ? send<HrDoc>('PUT', `/api/v1/hrdocs/${doc.id}`, payload) : send<HrDoc>('POST', '/api/v1/hrdocs', payload)
    },
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['hrdocs'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(`${LIST}/${r.id}`)
    },
  })
  const uploadFile = useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData()
      fd.append('file', file)
      return upload('PUT', `/api/v1/hrdocs/${doc?.id}/file`, fd)
    },
    onSuccess: () => {
      setError(null)
      void qc.invalidateQueries({ queryKey: ['hrdocs'] })
    },
    onError: (e) => setError(errorText(t, e)),
  })
  const removeFile = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/hrdocs/${doc?.id}/file`),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['hrdocs'] }),
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/hrdocs/${doc?.id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['hrdocs'] })
      navigate(LIST)
    },
    onError: (e) => setError(errorText(t, e)),
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  const toggle = (k: string) => setPicked(picked.includes(k) ? picked.filter((x) => x !== k) : [...picked, k])
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={doc ? t('hrdocs.edit') : t('hrdocs.add')} subtitle={doc?.title} backTo={doc ? `${LIST}/${doc.id}` : LIST} backLabel={t('hrdocs.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('hrdocs.main')}>
          <Field label={t('hrdocs.category')}>
            {(fid) => (
              <Select id={fid} value={category} onChange={(e) => setCategory(e.target.value as Category)}>
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {t(`hrdocs.cat.${c}`)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label={t('hrdocs.titleLabel')}>{(fid) => <Input id={fid} value={title} onChange={(e) => setTitle(e.target.value)} required minLength={2} maxLength={200} autoFocus />}</Field>
          <Field label={t('hrdocs.summary')}>{(fid) => <Input id={fid} value={summary} onChange={(e) => setSummary(e.target.value)} maxLength={300} />}</Field>
          <Field label={t('hrdocs.body')}>{(fid) => <textarea id={fid} value={body} onChange={(e) => setBody(e.target.value)} rows={14} className={area} />}</Field>
        </FormSection>
        <FormSection title={t('hrdocs.access')} description={t('hrdocs.accessHint')}>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4" checked={ack} onChange={(e) => setAck(e.target.checked)} />
            {t('hrdocs.requiresAck')}
          </label>
          <div className="flex flex-wrap gap-2">
            {roles.data?.map((r) => (
              <button key={r.key} type="button" aria-pressed={picked.includes(r.key)} onClick={() => toggle(r.key)} className={'rounded-full border px-3 py-1.5 text-xs ' + (picked.includes(r.key) ? 'border-primary bg-primary text-primary-fg' : 'border-border bg-surface text-muted')}>
                {i18n.language === 'ru' ? r.name_ru : r.name_uz}
              </button>
            ))}
          </div>
          <p className="text-xs text-muted">{picked.length ? t('hrdocs.rolesOnly') : t('hrdocs.rolesAll')}</p>
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : error}>
          <Button variant="outline" onClick={() => navigate(doc ? `${LIST}/${doc.id}` : LIST)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || title.trim().length < 2}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
      {doc && (
        <FormSection title={t('hrdocs.attachment')} description={t('hrdocs.attachmentHint')}>
          <div className="flex flex-wrap items-center gap-3">
            <input ref={fileRef} type="file" className="hidden" accept=".pdf,.docx,.xlsx,.png,.jpg,.jpeg" onChange={(e) => e.target.files?.[0] && uploadFile.mutate(e.target.files[0])} />
            <Button variant="outline" disabled={uploadFile.isPending} onClick={() => fileRef.current?.click()}>
              <BookOpen className="size-4" />
              {doc.has_file ? t('hrdocs.replaceFile') : t('hrdocs.uploadFile')}
            </Button>
            {doc.has_file && (
              <>
                <span className="text-sm text-muted">{doc.file_name}</span>
                <Button variant="ghost" className="text-danger" onClick={() => removeFile.mutate()}>
                  <Trash2 className="size-4" />
                </Button>
              </>
            )}
          </div>
        </FormSection>
      )}
      {doc && doc.version === 0 && (
        <FormSection title={t('org.dangerZone')} danger>
          <div>
            <Button
              variant="outline"
              className="text-danger"
              onClick={async () => {
                if (await confirm({ title: t('common.delete'), body: t('org.deleteConfirm', { name: doc.title }), danger: true, confirmLabel: t('common.delete') })) remove.mutate()
              }}
            >
              <Trash2 className="size-4" />
              {t('common.delete')}
            </Button>
          </div>
        </FormSection>
      )}
    </div>
  )
}
