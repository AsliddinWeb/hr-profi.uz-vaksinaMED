import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ShieldCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, PasswordInput } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import type { LetterDetail } from './api'

/** /letters/:id/write: xodim tushuntirish matnini yozib, parolini tasdiqlab (elektron imzo) topshiradi. */
export function WritePage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [text, setText] = useState('')
  const [password, setPassword] = useState('')
  const q = useQuery({ queryKey: ['letters', 'one', id], queryFn: () => api<LetterDetail>(`/api/v1/letters/${id}`), retry: false })
  const sign = useMutation({
    mutationFn: () => send('POST', `/api/v1/letters/${id}/submit`, { explanation: text, password }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['letters'] })
      toast.push({ title: t('letters.write.sent'), tone: 'success' })
      navigate(`/letters/${id}`, { replace: true })
    },
    onError: () => setPassword(''),
  })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const l = q.data
  if (!l) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (!l.can_write) return <Navigate to={`/letters/${id}`} replace />
  const submit = (e: FormEvent) => {
    e.preventDefault()
    sign.mutate()
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={t('letters.write.title')} subtitle={`${l.number} · ${t(`letters.incidents.${l.incident_type}`)}, ${formatDate(l.incident_date, i18n.language)}`} backTo={`/letters/${id}`} backLabel={l.number} />
      {(l.incident_note || l.instructions) && (
        <div className="rounded-card bg-surface-2 p-5 text-sm">
          {l.incident_note && <p className="whitespace-pre-wrap"><b>{t('letters.write.asked')}:</b> {l.incident_note}</p>}
          {l.instructions && <p className="mt-2 whitespace-pre-wrap text-muted">{l.instructions}</p>}
          {l.status === 'returned' && l.review_note && <p className="mt-2 text-danger">{t('letters.returnReason')}: {l.review_note}</p>}
        </div>
      )}
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('letters.write.explanation')} description={t('letters.write.hint')}>
          <Field label={t('letters.write.explanation')} hint={t('letters.write.min')}>
            {(fid) => <textarea id={fid} value={text} onChange={(e) => setText(e.target.value)} maxLength={5000} rows={9} required className="w-full rounded-control border border-border bg-surface px-3 py-2 text-sm" autoFocus />}
          </Field>
        </FormSection>
        <FormSection title={t('letters.write.signTitle')} description={t('letters.write.signHint')}>
          <Field label={t('letters.write.password')}>{(fid) => <PasswordInput id={fid} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />}</Field>
        </FormSection>
        <FormFooter error={sign.isError ? errorText(t, sign.error) : null}>
          <Button variant="outline" onClick={() => navigate(`/letters/${id}`)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={sign.isPending || text.trim().length < 10 || !password}>
            <ShieldCheck className="size-4" />
            {t('letters.write.submit')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
