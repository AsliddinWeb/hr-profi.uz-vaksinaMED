import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Paperclip } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send, upload } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { DOC_KINDS, formatSize, type EmployeeDocument } from './api'

/** /employees/:id/documents/new va /employees/:id/documents/:docId/edit */
export function DocumentFormPage() {
  const { id, docId } = useParams()
  const empId = Number(id)
  const doc = useQuery({
    queryKey: ['employees', 'document', empId, docId],
    queryFn: () => api<EmployeeDocument>(`/api/v1/employees/${empId}/documents/${docId}`),
    enabled: !!docId,
    retry: false,
  })
  if (!docId) return <DocumentForm empId={empId} doc={null} />
  if (doc.isLoading) return <Skeleton className="mx-auto h-80 max-w-3xl" />
  if (doc.error instanceof ApiError && doc.error.status === 404) return <NotFound />
  return doc.data ? <DocumentForm key={doc.data.id} empId={empId} doc={doc.data} /> : null
}

function DocumentForm({ empId, doc }: { empId: number; doc: EmployeeDocument | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [kind, setKind] = useState(doc?.kind ?? 'other')
  const [title, setTitle] = useState(doc?.title ?? '')
  const [file, setFile] = useState<File | null>(null)
  const [issued, setIssued] = useState(doc?.issued_at ?? '')
  const [expires, setExpires] = useState(doc?.expires_at ?? '')
  const [note, setNote] = useState(doc?.note ?? '')
  const back = `/employees/${empId}?tab=documents`

  const save = useMutation({
    mutationFn: () => {
      if (doc) {
        return send('PATCH', `/api/v1/employees/${empId}/documents/${doc.id}`, {
          kind,
          title,
          issued_at: issued || null,
          expires_at: expires || null,
          note: note || null,
        })
      }
      const f = new FormData()
      f.append('file', file as File)
      f.append('kind', kind)
      f.append('title', title)
      if (issued) f.append('issued_at', issued)
      if (expires) f.append('expires_at', expires)
      if (note) f.append('note', note)
      return upload('POST', `/api/v1/employees/${empId}/documents`, f)
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['employees', 'documents', empId] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(back)
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={doc ? t('employees.editDocument') : t('employees.addDocument')} backTo={back} backLabel={t('employees.toCard')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('employees.docFile')} description={doc ? undefined : t('employees.docFileHint')}>
          {doc ? (
            <p className="text-sm">
              {doc.filename} <span className="text-muted">· {formatSize(doc.size)}</span>
            </p>
          ) : (
            <label className="flex w-fit cursor-pointer items-center gap-2 rounded-control border border-dashed border-border px-4 py-3 text-sm hover:bg-surface-2">
              <Paperclip className="size-4" />
              {file ? `${file.name} · ${formatSize(file.size)}` : t('employees.chooseFile')}
              <input
                type="file"
                className="sr-only"
                accept=".pdf,.jpg,.jpeg,.png,.docx,.xlsx"
                onChange={(e) => {
                  const f = e.target.files?.[0] ?? null
                  setFile(f)
                  if (f && !title) setTitle(f.name.replace(/\.[^.]+$/, ''))
                }}
              />
            </label>
          )}
        </FormSection>
        <FormSection title={t('employees.sectionDetails')}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('employees.docKind')}>
              {(id) => (
                <Select id={id} value={kind} onChange={(e) => setKind(e.target.value)}>
                  {DOC_KINDS.map((k) => (
                    <option key={k} value={k}>
                      {t(`employees.docKinds.${k}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('employees.docTitle')}>{(id) => <Input id={id} value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={160} />}</Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('employees.issuedAt')}>{(id) => <Input id={id} type="date" value={issued} onChange={(e) => setIssued(e.target.value)} />}</Field>
            <Field label={t('employees.expiresAt')} hint={t('employees.expiresHint')}>
              {(id) => <Input id={id} type="date" value={expires} min={issued || undefined} onChange={(e) => setExpires(e.target.value)} />}
            </Field>
          </div>
          <Field label={t('employees.note')}>
            {(id) => <textarea id={id} value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} rows={3} className="w-full rounded-control border border-border bg-surface px-3 py-2 text-sm" />}
          </Field>
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(back)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !title.trim() || (!doc && !file)}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
