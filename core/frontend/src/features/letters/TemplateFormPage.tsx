import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Trash2 } from 'lucide-react'
import { useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText, fieldErrors } from '../auth/errorText'
import type { LetterTemplate } from './api'

const LIST = '/letters/templates'
const HOLDERS = ['employee_name', 'position', 'department', 'branch', 'incident_date', 'incident', 'explanation', 'date', 'company', 'number']

/** /letters/templates/new va /letters/templates/:id/edit */
export function TemplateFormPage() {
  const { id } = useParams()
  const tid = id ? Number(id) : null
  const tpl = useQuery({ queryKey: ['letters', 'templates', tid], queryFn: () => api<LetterTemplate>(`/api/v1/letters/templates/${tid}`), enabled: tid !== null, retry: false })
  if (tid === null) return <TemplateForm tpl={null} />
  if (tpl.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (tpl.error instanceof ApiError && tpl.error.status === 404) return <NotFound />
  if (!tpl.data) return null
  return <TemplateForm key={tpl.data.id} tpl={tpl.data} />
}

function TemplateForm({ tpl }: { tpl: LetterTemplate | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const bodyRef = useRef<HTMLTextAreaElement>(null)
  const [name, setName] = useState(tpl?.name ?? '')
  const [title, setTitle] = useState(tpl?.title ?? 'TUSHUNTIRISH XATI')
  const [recipient, setRecipient] = useState(tpl?.recipient_line ?? '{company} HR direktoriga')
  const [body, setBody] = useState(tpl?.body_template ?? "Men, {employee_name}, {incident_date} sanasidagi holat ({incident}) bo'yicha quyidagilarni tushuntiraman:\n\n{explanation}")
  const [instructions, setInstructions] = useState(tpl?.instructions ?? '')
  const [isDefault, setIsDefault] = useState(tpl?.is_default ?? false)
  const [active, setActive] = useState(tpl?.is_active ?? true)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const save = useMutation({
    mutationFn: () => {
      const payload = { name, title, recipient_line: recipient, body_template: body, instructions: instructions || null, is_default: isDefault, is_active: active }
      return tpl ? send('PUT', `/api/v1/letters/templates/${tpl.id}`, payload) : send('POST', '/api/v1/letters/templates', payload)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['letters'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(LIST)
    },
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/letters/templates/${tpl?.id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['letters'] })
      toast.push({ title: t('letters.templates.deleted'), tone: 'success' })
      navigate(LIST)
    },
    onError: (e) => setDeleteError(errorText(t, e)),
  })
  const fe = save.isError ? fieldErrors(t, save.error) : {}
  const insert = (key: string) => {
    const el = bodyRef.current
    const token = `{${key}}`
    if (!el) return setBody((b) => b + token)
    const [s, e] = [el.selectionStart, el.selectionEnd]
    setBody(body.slice(0, s) + token + body.slice(e))
    requestAnimationFrame(() => (el.focus(), el.setSelectionRange(s + token.length, s + token.length)))
  }
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  const apiErr = save.error instanceof ApiError && save.error.code !== 'validation' ? (save.error.code === 'unknown_placeholder' ? t('errors.unknown_placeholder', { names: String((save.error.extra.names as string[]).join(', ')) }) : errorText(t, save.error)) : null

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={tpl ? t('letters.templates.edit') : t('letters.templates.add')} subtitle={tpl?.name} backTo={LIST} backLabel={t('letters.templates.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('letters.templates.sectionMain')}>
          <Field label={t('letters.templates.name')} error={fe.name}>{(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} autoFocus />}</Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('letters.templates.docTitle')}>{(id) => <Input id={id} value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={160} />}</Field>
            <Field label={t('letters.templates.recipient')}>{(id) => <Input id={id} value={recipient} onChange={(e) => setRecipient(e.target.value)} maxLength={300} />}</Field>
          </div>
        </FormSection>
        <FormSection title={t('letters.templates.sectionBody')} description={t('letters.templates.bodyHint')}>
          <div className="flex flex-wrap gap-1.5" role="group" aria-label={t('letters.templates.placeholders')}>
            {HOLDERS.map((k) => (
              <button key={k} type="button" onClick={() => insert(k)} className="rounded-full border border-border bg-surface px-2.5 py-1 font-mono text-xs hover:bg-surface-2">
                {`{${k}}`}
              </button>
            ))}
          </div>
          <Field label={t('letters.templates.body')} error={fe.body_template}>
            {(id) => <textarea id={id} ref={bodyRef} value={body} onChange={(e) => setBody(e.target.value)} rows={10} required maxLength={5000} className="w-full rounded-control border border-border bg-surface px-3 py-2 font-mono text-sm" />}
          </Field>
          <Field label={t('letters.templates.instructions')} hint={t('letters.templates.instructionsHint')}>
            {(id) => <textarea id={id} value={instructions} onChange={(e) => setInstructions(e.target.value)} rows={3} maxLength={2000} className="w-full rounded-control border border-border bg-surface px-3 py-2 text-sm" />}
          </Field>
        </FormSection>
        <FormSection title={t('schedule.groups.sectionStatus')}>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4" checked={isDefault} disabled={tpl?.is_default} onChange={(e) => setIsDefault(e.target.checked)} />
            {t('letters.templates.makeDefault')}
          </label>
          {tpl && (
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="size-4" checked={active} disabled={tpl.is_default} onChange={(e) => setActive(e.target.checked)} />
              {t('schedule.activeLabel')}
            </label>
          )}
        </FormSection>
        <FormFooter error={apiErr}>
          <Button variant="outline" onClick={() => navigate(LIST)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !name.trim() || !body.includes('{explanation}')}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
      {tpl && (
        <FormSection title={t('org.dangerZone')} description={t('letters.templates.deleteHint')} danger>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              className="text-danger"
              disabled={remove.isPending}
              onClick={async () => {
                if (await confirm({ title: t('letters.templates.delete'), body: t('org.deleteConfirm', { name: tpl.name }), danger: true, confirmLabel: t('common.delete') })) {
                  setDeleteError(null)
                  remove.mutate()
                }
              }}
            >
              <Trash2 className="size-4" />
              {t('letters.templates.delete')}
            </Button>
            {deleteError && (
              <span role="alert" className="text-sm text-danger">
                {deleteError}
              </span>
            )}
          </div>
        </FormSection>
      )}
    </div>
  )
}
