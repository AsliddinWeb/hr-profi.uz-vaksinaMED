import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { DOC_KINDS, type Doc } from './api'

/** /logistics/vehicles/:vid/documents/new va /logistics/documents/:did/edit */
export function DocumentFormPage() {
  const { vid, did } = useParams()
  const docId = did ? Number(did) : null
  const q = useQuery({ queryKey: ['logistics', 'doc', docId], queryFn: () => api<Doc>(`/api/v1/logistics/documents/${docId}`), enabled: docId !== null, retry: false })
  if (docId === null) return <DocForm d={null} vehicleId={Number(vid)} />
  if (q.isLoading) return <Skeleton className="mx-auto h-72 max-w-3xl" />
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!q.data) return null
  return <DocForm key={q.data.id} d={q.data} vehicleId={q.data.vehicle_id} />
}

function DocForm({ d, vehicleId }: { d: Doc | null; vehicleId: number }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const back = `/logistics/vehicles/${vehicleId}`
  const [kind, setKind] = useState(d?.kind ?? 'insurance')
  const [number, setNumber] = useState(d?.number ?? '')
  const [issued, setIssued] = useState(d?.issued_at ?? '')
  const [expires, setExpires] = useState(d?.expires_at ?? '')
  const [note, setNote] = useState(d?.note ?? '')
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const save = useMutation({
    mutationFn: () => {
      const body = { kind, number: number || null, issued_at: issued || null, expires_at: expires, note: note || null }
      return d ? send<Doc>('PUT', `/api/v1/logistics/documents/${d.id}`, body) : send<Doc>('POST', `/api/v1/logistics/vehicles/${vehicleId}/documents`, body)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['logistics'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(back, { replace: true })
    },
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/logistics/documents/${d?.id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['logistics'] })
      toast.push({ title: t('logistics.doc.deleted'), tone: 'success' })
      navigate(back, { replace: true })
    },
    onError: (e) => setDeleteError(errorText(t, e)),
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={d ? t('logistics.doc.edit') : t('logistics.doc.add')} backTo={back} backLabel={t('logistics.vehicle.card')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('logistics.doc.title')} description={t('logistics.doc.hint')}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('logistics.doc.kind')}>
              {(id) => (
                <Select id={id} value={kind} onChange={(e) => setKind(e.target.value)}>
                  {DOC_KINDS.map((k) => (
                    <option key={k} value={k}>
                      {t(`logistics.docKind.${k}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('logistics.doc.number')}>{(id) => <Input id={id} value={number} onChange={(e) => setNumber(e.target.value)} maxLength={60} />}</Field>
            <Field label={t('logistics.doc.issued')}>{(id) => <Input id={id} type="date" value={issued} onChange={(e) => setIssued(e.target.value)} />}</Field>
            <Field label={t('logistics.doc.expires')}>{(id) => <Input id={id} type="date" value={expires} onChange={(e) => setExpires(e.target.value)} required />}</Field>
          </div>
          <Field label={t('recruit.candidate.note')}>{(id) => <Input id={id} value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} />}</Field>
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(back)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !expires}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
      {d && (
        <FormSection title={t('org.dangerZone')} danger>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              className="text-danger"
              disabled={remove.isPending}
              onClick={async () => {
                if (await confirm({ title: t('logistics.doc.delete'), body: t(`logistics.docKind.${d.kind}`), danger: true, confirmLabel: t('common.delete') })) {
                  setDeleteError(null)
                  remove.mutate()
                }
              }}
            >
              <Trash2 className="size-4" />
              {t('logistics.doc.delete')}
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
