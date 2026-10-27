import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { branchTitle, ROLES, type BranchCard } from './api'

/** /pharmacy/:id/edit: filial me'yori (lavozim bo'yicha kerakli xodim soni), ish vaqti va izoh. */
export function ProfileFormPage() {
  const id = Number(useParams().id)
  const q = useQuery({ queryKey: ['pharmacy', 'card', id], queryFn: () => api<BranchCard>(`/api/v1/pharmacy/branches/${id}`), retry: false })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!q.data) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  return <ProfileForm key={q.data.id} b={q.data} />
}

function ProfileForm({ b }: { b: BranchCard }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [norm, setNorm] = useState<Record<string, string>>(Object.fromEntries(ROLES.map((r) => [r, String(b.norm[r])])))
  const [is24h, setIs24h] = useState(b.hours.is_24h)
  const [open, setOpen] = useState(b.hours.open ?? '')
  const [close, setClose] = useState(b.hours.close ?? '')
  const [note, setNote] = useState(b.note ?? '')
  const back = `/pharmacy/${b.id}`

  const save = useMutation({
    mutationFn: () =>
      send('PUT', `/api/v1/pharmacy/branches/${b.id}/profile`, {
        staff_norm: Object.fromEntries(ROLES.map((r) => [r, Number(norm[r]) || 0])), is_24h: is24h,
        open_time: is24h ? null : open || null, close_time: is24h ? null : close || null, pharmacy_note: note || null,
      }), // fmt: skip
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['pharmacy'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(back)
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  const hoursInvalid = !is24h && (!!open !== !!close || (!!open && open === close))

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={t('pharmacy.profile.edit')} subtitle={branchTitle(b)} backTo={back} backLabel={branchTitle(b)} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('pharmacy.normTitle')} description={t('pharmacy.profile.normHint')}>
          <div className="grid gap-4 sm:grid-cols-3">
            {ROLES.map((r) => (
              <Field key={r} label={t(`pharmacy.roles.${r}`)} hint={t('pharmacy.profile.now', { count: b.counts[r] })}>
                {(id) => <Input id={id} type="number" min={0} max={50} value={norm[r]} onChange={(e) => setNorm({ ...norm, [r]: e.target.value })} />}
              </Field>
            ))}
          </div>
        </FormSection>
        <FormSection title={t('pharmacy.profile.hours')} description={t('pharmacy.profile.hoursHint')}>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4" checked={is24h} onChange={(e) => setIs24h(e.target.checked)} />
            {t('pharmacy.profile.h24')}
          </label>
          {!is24h && (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t('pharmacy.profile.open')} error={hoursInvalid ? t('pharmacy.profile.hoursInvalid') : null}>{(id) => <Input id={id} type="time" value={open} onChange={(e) => setOpen(e.target.value)} />}</Field>
              <Field label={t('pharmacy.profile.close')}>{(id) => <Input id={id} type="time" value={close} onChange={(e) => setClose(e.target.value)} />}</Field>
            </div>
          )}
        </FormSection>
        <FormSection title={t('employees.note')}>
          <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={4} maxLength={2000} aria-label={t('employees.note')} className="w-full rounded-control border border-border bg-surface px-3 py-2 text-sm" />
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(back)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || hoursInvalid}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
