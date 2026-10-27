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
import { addDays, todayLocal } from '../attendance/api'
import { errorText } from '../auth/errorText'
import type { ScanResult } from './api'

/** /penalties/scan: o'tgan kunlar davomatidan jarimalarni hisoblash (avval ko'rib chiqish, keyin yozish). */
export function ScanPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [yesterday] = useState(() => addDays(todayLocal(), -1))
  const [start, setStart] = useState(() => addDays(todayLocal(), -7))
  const [end, setEnd] = useState(yesterday)
  const [preview, setPreview] = useState<ScanResult | null>(null)

  const run = useMutation({
    mutationFn: (dry: boolean) => send<ScanResult>('POST', '/api/v1/penalties/scan', { start, end, dry_run: dry }),
    onSuccess: (r, dry) => {
      if (dry) return setPreview(r)
      void qc.invalidateQueries({ queryKey: ['penalties'] })
      toast.push({ title: t('penalties.scan.done', { count: r.created }), tone: 'success' })
      navigate('/penalties')
    },
  })
  const valid = !!start && !!end && end >= start && end <= yesterday
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (valid) run.mutate(true)
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={t('penalties.scan.title')} subtitle={t('penalties.scan.subtitle')} backTo="/penalties" backLabel={t('penalties.title')} />
      <form onSubmit={submit} onChange={() => setPreview(null)} className="flex flex-col gap-6">
        <FormSection title={t('penalties.scan.period')} description={t('penalties.scan.hint')}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('schedule.apply.from')}>{(id) => <Input id={id} type="date" value={start} max={yesterday} onChange={(e) => setStart(e.target.value)} required />}</Field>
            <Field label={t('schedule.apply.to')} error={end > yesterday ? t('errors.range_not_finished') : null}>
              {(id) => <Input id={id} type="date" value={end} max={yesterday} min={start} onChange={(e) => setEnd(e.target.value)} required />}
            </Field>
          </div>
        </FormSection>
        {preview && (
          <Card tint={preview.created ? 'sand' : 'mint'} className="p-5" role="status">
            <h2 className="font-semibold">{t('penalties.scan.preview', { v: preview.rule_version })}</h2>
            <dl className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-5">
              {(['created', 'warnings', 'fines', 'blocks', 'existing'] as const).map((k) => (
                <div key={k}>
                  <dt className="text-muted">{t(`penalties.scan.${k}`)}</dt>
                  <dd className="mt-0.5 text-2xl font-semibold tabular-nums">{preview[k]}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-3 text-xs text-muted">{t('penalties.scan.note')}</p>
          </Card>
        )}
        <FormFooter error={run.isError ? errorText(t, run.error) : null}>
          <Button variant="outline" onClick={() => navigate('/penalties')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" variant="outline" disabled={!valid || run.isPending}>
            {t('schedule.apply.previewBtn')}
          </Button>
          <Button disabled={!valid || !preview || preview.created === 0 || run.isPending} onClick={() => run.mutate(false)}>
            {t('penalties.scan.run', { count: preview?.created ?? 0 })}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
