import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, FileDown, Plus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { formatDate, formatDateTime } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import { EmployeePicker, type Picked } from '../retention/EmployeePicker'
import { APP_TYPES, ORDER_TYPES, STAFF_TONE, type StaffDoc } from './api'

const area = 'w-full rounded-control border border-border bg-surface px-3 py-2 text-sm'
const LIST = '/hr/documents'

/** /hr/documents: arizalar va buyruqlar (xodim o'zinikini, HR hammasini ko'radi). */
export function StaffDocsPage() {
  const { t, i18n } = useTranslation()
  const can = useCan()
  const [kind, setKind] = useState<'' | 'application' | 'order'>('')
  const [q, setQ] = useState('')
  const list = useQuery({ queryKey: ['staffdocs', 'list', kind, q], queryFn: () => api<{ items: StaffDoc[]; total: number; pending_applications: number }>(`/api/v1/staffdocs?${kind ? `kind=${kind}&` : ''}${q.trim() ? `q=${encodeURIComponent(q.trim())}` : ''}`), placeholderData: (p) => p, refetchInterval: 60_000 })
  const pill = (on: boolean) => 'rounded-full border px-3 py-1.5 text-xs font-medium ' + (on ? 'border-primary bg-primary text-primary-fg' : 'border-border bg-surface text-muted hover:text-text')
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title={t('staffdocs.title')}
        subtitle={t('staffdocs.subtitle')}
        actions={
          <div className="flex gap-2">
            {can('staffdocs.apply') && (
              <Link to={`${LIST}/application/new`}>
                <Button variant={can('staffdocs.manage') ? 'outline' : 'primary'}>
                  <Plus className="size-4" />
                  {t('staffdocs.newApp')}
                </Button>
              </Link>
            )}
            {can('staffdocs.manage') && (
              <Link to={`${LIST}/order/new`}>
                <Button>
                  <Plus className="size-4" />
                  {t('staffdocs.newOrder')}
                </Button>
              </Link>
            )}
          </div>
        }
      />
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex gap-2">
          {(['', 'application', 'order'] as const).map((k) => (
            <button key={k} className={pill(kind === k)} aria-pressed={kind === k} onClick={() => setKind(k)}>
              {t(`staffdocs.kind.${k || 'all'}`)}
            </button>
          ))}
        </div>
        <Input className="w-64" placeholder={t('staffdocs.search')} value={q} onChange={(e) => setQ(e.target.value)} />
        {!!list.data?.pending_applications && <Badge tone="warning">{t('staffdocs.pendingApps', { n: list.data.pending_applications })}</Badge>}
      </div>
      {!list.data ? (
        <Skeleton className="h-40" />
      ) : (
        <div className="flex flex-col gap-3">
          {list.data.items.map((d) => (
            <Link key={d.id} to={`${LIST}/${d.id}`}>
              <Card className="flex flex-wrap items-center justify-between gap-3 p-4 hover:bg-surface-2">
                <div>
                  <div className="font-medium">
                    {d.title} <span className="text-xs font-normal text-muted">{d.number ?? t('staffdocs.draftNo')}</span>
                  </div>
                  <div className="text-sm text-muted">
                    {d.employee.name} · {t(`staffdocs.kind.${d.kind}`)} · {formatDate(d.created_at, i18n.language)}
                    {d.start_date ? ` · ${formatDate(d.start_date, i18n.language)}${d.end_date && d.end_date !== d.start_date ? ` – ${formatDate(d.end_date, i18n.language)}` : ''}` : ''}
                  </div>
                </div>
                <Badge tone={STAFF_TONE[d.status]}>{t(`staffdocs.status.${d.status}`)}</Badge>
              </Card>
            </Link>
          ))}
          {list.data.items.length === 0 && <Card className="p-8 text-center text-muted">{t('common.empty')}</Card>}
        </div>
      )}
    </div>
  )
}

/** /hr/documents/application/new: xodim ariza yozadi. */
export function ApplicationFormPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [subtype, setSubtype] = useState<(typeof APP_TYPES)[number]>('vacation')
  const [body, setBody] = useState('')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const needsDates = subtype === 'vacation' || subtype === 'unpaid'
  const save = useMutation({
    mutationFn: () => send<StaffDoc>('POST', '/api/v1/staffdocs/applications', { subtype, body, start_date: start || null, end_date: end || null }),
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['staffdocs'] })
      toast.push({ title: t('staffdocs.appSent'), tone: 'success' })
      navigate(`${LIST}/${r.id}`, { replace: true })
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={t('staffdocs.newApp')} subtitle={t('staffdocs.appHint')} backTo={LIST} backLabel={t('staffdocs.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('staffdocs.appMain')}>
          <Field label={t('staffdocs.type')}>
            {(fid) => (
              <Select id={fid} value={subtype} onChange={(e) => setSubtype(e.target.value as typeof subtype)}>
                {APP_TYPES.map((s) => (
                  <option key={s} value={s}>
                    {t(`staffdocs.appTypes.${s}`)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          {(needsDates || start || end) && (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t('staffdocs.from')}>{(fid) => <Input id={fid} type="date" value={start} onChange={(e) => setStart(e.target.value)} required={needsDates} />}</Field>
              <Field label={t('staffdocs.to')}>{(fid) => <Input id={fid} type="date" value={end} min={start} onChange={(e) => setEnd(e.target.value)} />}</Field>
            </div>
          )}
          <Field label={t('staffdocs.text')}>{(fid) => <textarea id={fid} value={body} onChange={(e) => setBody(e.target.value)} rows={7} maxLength={5000} className={area} required />}</Field>
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(LIST)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || body.trim().length < 3 || (needsDates && !start)}>
            {t('staffdocs.send')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}

/** /hr/documents/order/new (?employee=&application=) va /hr/documents/:id/edit (qoralama buyruq). */
export function OrderFormPage() {
  const { id } = useParams()
  const did = id ? Number(id) : null
  const q = useQuery({ queryKey: ['staffdocs', 'one', did], queryFn: () => api<StaffDoc>(`/api/v1/staffdocs/${did}`), enabled: did !== null, retry: false })
  if (did === null) return <OrderForm doc={null} />
  if (q.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  return q.data ? <OrderForm key={q.data.id} doc={q.data} /> : null
}

function OrderForm({ doc }: { doc: StaffDoc | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [params] = useSearchParams()
  const preEmp = Number(params.get('employee')) || null
  const preApp = Number(params.get('application')) || null
  const pre = useQuery({ queryKey: ['staffdocs', 'one', preApp], queryFn: () => api<StaffDoc>(`/api/v1/staffdocs/${preApp}`), enabled: !!preApp && !doc })
  const [emp, setEmp] = useState<Picked | null>(doc ? doc.employee : null)
  const picked = emp ?? (pre.data ? pre.data.employee : preEmp ? { id: preEmp, name: `#${preEmp}` } : null)
  const [subtype, setSubtype] = useState<(typeof ORDER_TYPES)[number]>(((): (typeof ORDER_TYPES)[number] => (doc?.subtype as (typeof ORDER_TYPES)[number]) ?? 'vacation')())
  const [title, setTitle] = useState(doc?.title ?? '')
  const [body, setBody] = useState(doc?.body ?? '')
  const [start, setStart] = useState(doc?.start_date ?? pre.data?.start_date ?? '')
  const [end, setEnd] = useState(doc?.end_date ?? pre.data?.end_date ?? '')
  const save = useMutation({
    mutationFn: () =>
      doc
        ? send<StaffDoc>('PUT', `/api/v1/staffdocs/${doc.id}`, { title, body, start_date: start || null, end_date: end || null })
        : send<StaffDoc>('POST', '/api/v1/staffdocs/orders', { employee_id: picked?.id, subtype, title: title || null, body: body || null, start_date: start || null, end_date: end || null, related_id: preApp }),
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['staffdocs'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(`${LIST}/${r.id}`, { replace: true })
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={doc ? t('staffdocs.editOrder') : t('staffdocs.newOrder')} subtitle={t('staffdocs.orderHint')} backTo={doc ? `${LIST}/${doc.id}` : LIST} backLabel={t('staffdocs.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('staffdocs.orderMain')}>
          {doc ? <p className="text-sm font-medium">{doc.employee.name}</p> : <EmployeePicker value={picked} onChange={setEmp} />}
          {!doc && (
            <Field label={t('staffdocs.type')}>
              {(fid) => (
                <Select id={fid} value={subtype} onChange={(e) => setSubtype(e.target.value as typeof subtype)}>
                  {ORDER_TYPES.map((s) => (
                    <option key={s} value={s}>
                      {t(`staffdocs.orderTypes.${s}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('staffdocs.from')}>{(fid) => <Input id={fid} type="date" value={start} onChange={(e) => setStart(e.target.value)} />}</Field>
            <Field label={t('staffdocs.to')}>{(fid) => <Input id={fid} type="date" value={end} min={start} onChange={(e) => setEnd(e.target.value)} />}</Field>
          </div>
          <Field label={t('staffdocs.titleLabel')}>{(fid) => <Input id={fid} value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} placeholder={t('staffdocs.titleAuto')} required={!!doc} />}</Field>
          <Field label={t('staffdocs.orderText')}>{(fid) => <textarea id={fid} value={body} onChange={(e) => setBody(e.target.value)} rows={8} maxLength={8000} className={area} placeholder={t('staffdocs.orderTextAuto')} required={!!doc} />}</Field>
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(LIST)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !picked}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}

/** /hr/documents/:id: ariza/buyruq tafsiloti: qaror, imzo, tanishish, PDF. */
export function StaffDocDetailPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [note, setNote] = useState('')
  const [password, setPassword] = useState('')
  const q = useQuery({ queryKey: ['staffdocs', 'one', id], queryFn: () => api<StaffDoc>(`/api/v1/staffdocs/${id}`), retry: false })
  const act = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: unknown }) => send<StaffDoc>('POST', `/api/v1/staffdocs/${id}/${path}`, body),
    onSuccess: () => {
      setNote('')
      setPassword('')
      void qc.invalidateQueries({ queryKey: ['staffdocs'] })
    },
  })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!q.data) return <Skeleton className="mx-auto h-64 max-w-3xl" />
  const d = q.data
  const row = (label: string, value: string | null | undefined) =>
    value ? (
      <div className="flex justify-between gap-4 text-sm">
        <span className="text-muted">{label}</span>
        <span className="text-right font-medium">{value}</span>
      </div>
    ) : null
  const period = d.start_date ? `${formatDate(d.start_date, i18n.language)}${d.end_date && d.end_date !== d.start_date ? ` – ${formatDate(d.end_date, i18n.language)}` : ''}` : null
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <PageHeader
        title={d.title}
        subtitle={`${d.number ?? t('staffdocs.draftNo')} · ${d.employee.name}`}
        backTo={LIST}
        backLabel={t('staffdocs.title')}
        actions={
          <div className="flex items-center gap-2">
            <Badge tone={STAFF_TONE[d.status]}>{t(`staffdocs.status.${d.status}`)}</Badge>
            {d.has_pdf && (
              <a href={`/api/v1/staffdocs/${d.id}/pdf?lang=${i18n.language === 'ru' ? 'ru' : 'uz'}`} download>
                <Button variant="outline">
                  <FileDown className="size-4" />
                  PDF
                </Button>
              </a>
            )}
          </div>
        }
      />
      <Card className="flex flex-col gap-3 p-6">
        <div className="whitespace-pre-wrap text-sm leading-relaxed">{d.body}</div>
        <div className="mt-2 flex flex-col gap-1.5 border-t border-border pt-3">
          {row(t('staffdocs.period'), period)}
          {row(t('staffdocs.createdBy'), d.created_by)}
          {row(t('staffdocs.decidedBy'), d.decided_by && `${d.decided_by}${d.decided_at ? ' · ' + formatDateTime(d.decided_at, i18n.language) : ''}`)}
          {row(t('staffdocs.decisionNote'), d.decision_note)}
          {row(t('staffdocs.signedBy'), d.signed_by && `${d.signed_by}${d.signed_at ? ' · ' + formatDateTime(d.signed_at, i18n.language) : ''}`)}
          {row(t('staffdocs.acknowledged'), d.acknowledged_at && formatDateTime(d.acknowledged_at, i18n.language))}
        </div>
      </Card>
      {act.isError && (
        <p role="alert" className="text-sm text-danger">
          {errorText(t, act.error)}
        </p>
      )}
      {d.can.decide && (
        <Card className="flex flex-col gap-3 p-5">
          <Field label={t('staffdocs.decisionNote')}>{(fid) => <textarea id={fid} value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={1000} className={area} />}</Field>
          <div className="flex gap-2">
            <Button disabled={act.isPending} onClick={() => act.mutate({ path: 'decide', body: { action: 'approve', note: note || null } })}>
              {t('staffdocs.approve')}
            </Button>
            <Button variant="outline" className="text-danger" disabled={act.isPending || !note.trim()} onClick={() => act.mutate({ path: 'decide', body: { action: 'reject', note } })}>
              {t('staffdocs.reject')}
            </Button>
          </div>
        </Card>
      )}
      {d.can.make_order && (
        <div>
          <Link to={`${LIST}/order/new?employee=${d.employee.id}&application=${d.id}`}>
            <Button variant="outline">{t('staffdocs.makeOrder')}</Button>
          </Link>
        </div>
      )}
      {d.can.sign && (
        <Card className="flex flex-col gap-3 p-5">
          <p className="text-sm text-muted">{t('staffdocs.signHint')}</p>
          <Field label={t('staffdocs.password')}>{(fid) => <Input id={fid} type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />}</Field>
          <div>
            <Button disabled={act.isPending || !password} onClick={() => act.mutate({ path: 'sign', body: { password } })}>
              <Check className="size-4" />
              {t('staffdocs.sign')}
            </Button>
          </div>
        </Card>
      )}
      <div className="flex flex-wrap gap-2">
        {d.can.edit && (
          <Button variant="outline" onClick={() => navigate(`${LIST}/${d.id}/edit`)}>
            {t('common.edit')}
          </Button>
        )}
        {d.can.ack && (
          <Button disabled={act.isPending} onClick={() => act.mutate({ path: 'ack' })}>
            <Check className="size-4" />
            {t('staffdocs.ack')}
          </Button>
        )}
        {d.can.cancel && (
          <Button variant="outline" className="text-danger" disabled={act.isPending} onClick={() => act.mutate({ path: 'cancel' })}>
            {t('staffdocs.cancel')}
          </Button>
        )}
      </div>
    </div>
  )
}
