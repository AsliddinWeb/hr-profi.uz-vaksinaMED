import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, send } from '../../lib/api'
import { errorText, fieldErrors } from '../auth/errorText'
import type { AiSettings } from './api'

/** /ai/settings: AI ni yoqish/o'chirish, model, kunlik limit va funksiyalar. */
export function SettingsPage() {
  const q = useQuery({ queryKey: ['ai', 'settings'], queryFn: () => api<AiSettings>('/api/v1/ai/settings') })
  if (!q.data) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  return <SettingsForm s={q.data} />
}

function SettingsForm({ s }: { s: AiSettings }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [enabled, setEnabled] = useState(s.enabled)
  const [model, setModel] = useState(s.model)
  const [limit, setLimit] = useState(String(s.daily_limit))
  const [features, setFeatures] = useState(s.features)
  const save = useMutation({
    mutationFn: () => send<AiSettings>('PUT', '/api/v1/ai/settings', { enabled, model, daily_limit: Number(limit) || 1, features }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['ai'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate('/ai/usage')
    },
  })
  const fe = save.isError ? fieldErrors(t, save.error) : {}
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={t('ai.settings.title')} subtitle={t('ai.settings.subtitle')} backTo="/ai/usage" backLabel={t('ai.usage.title')} />
      {!s.configured && (
        <p role="alert" className="rounded-card border border-warning/40 bg-warning/10 p-4 text-sm">
          {t('ai.settings.noKey')}
        </p>
      )}
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('ai.settings.main')}>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
            {t('ai.settings.enabled')}
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('ai.settings.model')} hint={t('ai.settings.modelHint')} error={fe.model}>{(id) => <Input id={id} value={model} onChange={(e) => setModel(e.target.value)} required maxLength={80} />}</Field>
            <Field label={t('ai.settings.limit')} hint={t('ai.settings.limitHint')} error={fe.daily_limit}>{(id) => <Input id={id} type="number" min={1} max={1000} value={limit} onChange={(e) => setLimit(e.target.value)} />}</Field>
          </div>
        </FormSection>
        <FormSection title={t('ai.settings.features')} description={t('ai.settings.featuresHint')}>
          {(['summary', 'resume', 'ticket'] as const).map((f) => (
            <label key={f} className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="size-4" checked={features[f]} onChange={(e) => setFeatures({ ...features, [f]: e.target.checked })} />
              {t(`ai.feature.${f}`)}
            </label>
          ))}
        </FormSection>
        <FormFooter error={save.isError && !Object.keys(fe).length ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate('/ai/usage')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || model.trim().length < 3}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
