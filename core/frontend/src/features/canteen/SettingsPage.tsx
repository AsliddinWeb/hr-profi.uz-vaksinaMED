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
import { errorText } from '../auth/errorText'

interface Settings {
  require_qr: boolean
  rating_days: number
}

/** /canteen/settings: baholash qoidalari. */
export function SettingsPage() {
  const q = useQuery({ queryKey: ['canteen', 'settings'], queryFn: () => api<Settings>('/api/v1/canteen/settings') })
  if (!q.data) return <Skeleton className="mx-auto h-72 max-w-3xl" />
  return <Form s={q.data} />
}

function Form({ s }: { s: Settings }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [requireQr, setRequireQr] = useState(s.require_qr)
  const [days, setDays] = useState(String(s.rating_days))
  const save = useMutation({
    mutationFn: () => send('PUT', '/api/v1/canteen/settings', { require_qr: requireQr, rating_days: Number(days) || 0 }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['canteen'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate('/canteen/qr')
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={t('canteen.settings.title')} backTo="/canteen/qr" backLabel={t('canteen.qr.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('canteen.settings.rules')}>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" className="mt-0.5 size-4" checked={requireQr} onChange={(e) => setRequireQr(e.target.checked)} />
            <span>
              {t('canteen.settings.requireQr')}
              <span className="block text-xs text-muted">{t('canteen.settings.requireQrHint')}</span>
            </span>
          </label>
          <Field label={t('canteen.settings.ratingDays')} hint={t('canteen.settings.ratingDaysHint')}>{(id) => <Input id={id} type="number" min={0} max={14} value={days} onChange={(e) => setDays(e.target.value)} />}</Field>
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate('/canteen/qr')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
