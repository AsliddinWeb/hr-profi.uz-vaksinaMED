import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText, fieldErrors } from '../auth/errorText'
import { Sparkles } from 'lucide-react'
import { useAiStatus } from '../ai/useAiStatus'
import { PRIORITIES, SLA_HOURS, type Category, type Ticket, type TicketDetail } from './api'

/** /helpdesk/new va /helpdesk/:id/edit */
export function FormPage() {
  const { id } = useParams()
  const ticketId = id ? Number(id) : null
  const q = useQuery({ queryKey: ['helpdesk', 'one', ticketId], queryFn: () => api<TicketDetail>(`/api/v1/helpdesk/${ticketId}`), enabled: ticketId !== null, retry: false })
  if (ticketId === null) return <TicketForm ticket={null} />
  if (q.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!q.data) return null
  return <TicketForm key={q.data.id} ticket={q.data} />
}

function TicketForm({ ticket }: { ticket: TicketDetail | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [title, setTitle] = useState(ticket?.title ?? '')
  const [description, setDescription] = useState(ticket?.description ?? '')
  const [categoryId, setCategoryId] = useState(String(ticket?.category?.id ?? ''))
  const [branchId, setBranchId] = useState(String(ticket?.branch?.id ?? ''))
  const [priority, setPriority] = useState<string>(ticket?.priority ?? 'normal')
  const [device, setDevice] = useState(ticket?.device_info ?? '')
  const cats = useQuery({ queryKey: ['helpdesk', 'categories'], queryFn: () => api<Category[]>('/api/v1/helpdesk/categories') })
  const branches = useQuery({ queryKey: ['helpdesk', 'branches'], queryFn: () => api<{ id: number; name: string }[]>('/api/v1/helpdesk/branches') })
  const ai = useAiStatus().data
  const suggest = useMutation({
    mutationFn: () => send<{ fields: { title?: string; category_id?: number; priority?: string } }>('POST', '/api/v1/ai/ticket-suggest', { text: `${title}\n${description}` }),
    onSuccess: ({ fields }) => {
      if (fields.title && !title.trim()) setTitle(fields.title)
      if (fields.category_id) setCategoryId(String(fields.category_id))
      if (fields.priority) setPriority(fields.priority)
    },
  })
  const cat = cats.data?.find((c) => String(c.id) === categoryId)

  const save = useMutation({
    mutationFn: () => {
      const body = { title, description: description || null, category_id: categoryId ? Number(categoryId) : null, branch_id: branchId ? Number(branchId) : null, priority, device_info: device || null }
      return ticket ? send<Ticket>('PUT', `/api/v1/helpdesk/${ticket.id}`, body) : send<Ticket>('POST', '/api/v1/helpdesk', body)
    },
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['helpdesk'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(`/helpdesk/${r.id}`, { replace: true })
    },
  })
  const fe = save.isError ? fieldErrors(t, save.error) : {}
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={ticket ? t('helpdesk.edit') : t('helpdesk.new')} subtitle={ticket?.number} backTo={ticket ? `/helpdesk/${ticket.id}` : '/helpdesk'} backLabel={ticket ? ticket.number : t('helpdesk.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('helpdesk.form.main')}>
          <Field label={t('helpdesk.form.title')} error={fe.title}>{(id) => <Input id={id} value={title} onChange={(e) => setTitle(e.target.value)} required minLength={3} maxLength={200} autoFocus />}</Field>
          <Field label={t('helpdesk.form.description')} hint={t('helpdesk.form.descriptionHint')}>
            {(id) => <textarea id={id} value={description} onChange={(e) => setDescription(e.target.value)} rows={6} maxLength={10000} className="w-full rounded-control border border-border bg-surface px-3 py-2 text-sm" />}
          </Field>
          {ai?.enabled && ai.features.ticket && !ticket && (
            <div className="flex flex-wrap items-center gap-3">
              <Button variant="outline" disabled={suggest.isPending || (title + description).trim().length < 10} onClick={() => suggest.mutate()}>
                <Sparkles className="size-4" />
                {suggest.isPending ? t('ai.ticket.working') : t('ai.ticket.run')}
              </Button>
              <span className="text-xs text-muted">{suggest.isError ? errorText(t, suggest.error) : suggest.isSuccess ? t('ai.ticket.done') : t('ai.ticket.hint')}</span>
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('helpdesk.category')} hint={cat?.default_assignee ? t('helpdesk.form.autoAssign', { name: cat.default_assignee.name }) : undefined}>
              {(id) => (
                <Select id={id} value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
                  <option value="">{t('helpdesk.noCategory')}</option>
                  {cats.data?.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('helpdesk.branch')}>
              {(id) => (
                <Select id={id} value={branchId} onChange={(e) => setBranchId(e.target.value)}>
                  <option value="">—</option>
                  {branches.data?.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('tasks.priorityLabel')} hint={t('helpdesk.form.slaHint', { hours: SLA_HOURS[priority as keyof typeof SLA_HOURS] })}>
              {(id) => (
                <Select id={id} value={priority} onChange={(e) => setPriority(e.target.value)}>
                  {PRIORITIES.map((p) => (
                    <option key={p} value={p}>
                      {t(`tasks.priority.${p}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('helpdesk.form.device')} hint={t('helpdesk.form.deviceHint')}>{(id) => <Input id={id} value={device} onChange={(e) => setDevice(e.target.value)} maxLength={200} />}</Field>
          </div>
        </FormSection>
        <FormFooter error={save.isError && !Object.keys(fe).length ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(ticket ? `/helpdesk/${ticket.id}` : '/helpdesk')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || title.trim().length < 3}>
            {ticket ? t('common.save') : t('helpdesk.form.submit')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
