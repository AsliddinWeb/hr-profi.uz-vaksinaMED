import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Card } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input } from '../../components/ui/Input'
import { useToast } from '../../components/ui/toastContext'
import { send } from '../../lib/api'
import { errorText } from '../auth/errorText'
import { ROLES } from './api'

/** /pharmacy/norms: barcha (yoki hali belgilanmagan) filiallarga bir xil me'yor va ish vaqtini qo'llash. */
export function NormsBulkPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [norm, setNorm] = useState<Record<string, string>>({ manager: '1', pharmacist: '2', intern: '0' })
  const [applyHours, setApplyHours] = useState(false)
  const [is24h, setIs24h] = useState(false)
  const [open, setOpen] = useState('09:00')
  const [close, setClose] = useState('21:00')
  const [onlyUnset, setOnlyUnset] = useState(false)
  const [preview, setPreview] = useState<number | null>(null)

  const body = (dry: boolean) => ({
    staff_norm: Object.fromEntries(ROLES.map((r) => [r, Number(norm[r]) || 0])), hours: applyHours, is_24h: is24h,
    open_time: applyHours && !is24h ? open : null, close_time: applyHours && !is24h ? close : null, only_unset: onlyUnset, dry_run: dry,
  }) // fmt: skip
  const run = useMutation({
    mutationFn: (dry: boolean) => send<{ branches: number; applied: boolean }>('POST', '/api/v1/pharmacy/norms/bulk', body(dry)),
    onSuccess: (r, dry) => {
      if (dry) return setPreview(r.branches)
      void qc.invalidateQueries({ queryKey: ['pharmacy'] })
      toast.push({ title: t('pharmacy.norms.done', { count: r.branches }), tone: 'success' })
      navigate('/pharmacy')
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    run.mutate(true)
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={t('pharmacy.norms.title')} subtitle={t('pharmacy.norms.subtitle')} backTo="/pharmacy" backLabel={t('pharmacy.title')} />
      <form onSubmit={submit} onChange={() => setPreview(null)} className="flex flex-col gap-6">
        <FormSection title={t('pharmacy.normTitle')}>
          <div className="grid gap-4 sm:grid-cols-3">
            {ROLES.map((r) => (
              <Field key={r} label={t(`pharmacy.roles.${r}`)}>{(id) => <Input id={id} type="number" min={0} max={50} value={norm[r]} onChange={(e) => setNorm({ ...norm, [r]: e.target.value })} />}</Field>
            ))}
          </div>
        </FormSection>
        <FormSection title={t('pharmacy.profile.hours')}>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4" checked={applyHours} onChange={(e) => setApplyHours(e.target.checked)} />
            {t('pharmacy.norms.applyHours')}
          </label>
          {applyHours && (
            <>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" className="size-4" checked={is24h} onChange={(e) => setIs24h(e.target.checked)} />
                {t('pharmacy.profile.h24')}
              </label>
              {!is24h && (
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label={t('pharmacy.profile.open')}>{(id) => <Input id={id} type="time" value={open} onChange={(e) => setOpen(e.target.value)} required />}</Field>
                  <Field label={t('pharmacy.profile.close')}>{(id) => <Input id={id} type="time" value={close} onChange={(e) => setClose(e.target.value)} required />}</Field>
                </div>
              )}
            </>
          )}
        </FormSection>
        <FormSection title={t('pharmacy.norms.scope')}>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" className="mt-0.5 size-4" checked={onlyUnset} onChange={(e) => setOnlyUnset(e.target.checked)} />
            <span>
              {t('pharmacy.norms.onlyUnset')}
              <span className="block text-xs text-muted">{t('pharmacy.norms.onlyUnsetHint')}</span>
            </span>
          </label>
        </FormSection>
        {preview !== null && (
          <Card tint={preview ? 'sand' : 'mint'} className="p-5" role="status">
            {t('pharmacy.norms.preview', { count: preview })}
          </Card>
        )}
        <FormFooter error={run.isError ? errorText(t, run.error) : null}>
          <Button variant="outline" onClick={() => navigate('/pharmacy')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" variant="outline" disabled={run.isPending}>
            {t('schedule.apply.previewBtn')}
          </Button>
          <Button disabled={run.isPending || preview === null || preview === 0} onClick={() => run.mutate(false)}>
            {t('pharmacy.norms.apply', { count: preview ?? 0 })}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
