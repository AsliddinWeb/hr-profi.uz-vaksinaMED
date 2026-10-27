import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input } from '../../components/ui/Input'
import { useToast } from '../../components/ui/toastContext'
import { send } from '../../lib/api'
import { errorText } from '../auth/errorText'
import { currentPeriod } from './api'

interface Result {
  ok: boolean
  valid: number
  errors: { row: number; code: string }[]
  imported: number
}

/** /payroll/items/import: CSV matnini joylab, avval tekshirish, keyin kiritish. */
export function ItemsImportPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [sp] = useSearchParams()
  const [period, setPeriod] = useState(sp.get('period') ?? currentPeriod())
  const [csv, setCsv] = useState('')
  const [checked, setChecked] = useState<Result | null>(null)
  const run = useMutation({
    mutationFn: (dry: boolean) => send<Result>('POST', '/api/v1/payroll/items/import', { period, csv, dry_run: dry }),
    onSuccess: (r, dry) => {
      if (dry) return setChecked(r)
      void qc.invalidateQueries({ queryKey: ['payroll'] })
      toast.push({ title: t('payroll.import.done', { count: r.imported }), tone: 'success' })
      navigate('/payroll/items', { replace: true })
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    run.mutate(true)
  }
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={t('payroll.item.import')} subtitle={t('payroll.import.hint')} backTo="/payroll/items" backLabel={t('payroll.tabs.items')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('payroll.import.data')} description={t('payroll.import.format')}>
          <Field label={t('payroll.run.period')}>{(id) => <Input id={id} type="month" value={period} onChange={(e) => (setPeriod(e.target.value), setChecked(null))} required />}</Field>
          <textarea value={csv} onChange={(e) => (setCsv(e.target.value), setChecked(null))} rows={10} aria-label="CSV" placeholder={'xodim_no;tur;summa;izoh\n12;sales;45000000;Noyabr savdosi\n12;kpi;85'} className="w-full rounded-control border border-border bg-surface px-3 py-2 font-mono text-sm" />
        </FormSection>
        {checked && (
          <Card tint={checked.ok ? 'mint' : 'rose'} className="p-5 text-sm" role="status">
            <p className="font-medium">{checked.ok ? t('payroll.import.valid', { count: checked.valid }) : t('payroll.import.invalid', { count: checked.errors.length })}</p>
            {checked.errors.length > 0 && (
              <ul className="mt-2 list-disc pl-5">
                {checked.errors.map((e) => (
                  <li key={e.row}>
                    {t('payroll.import.row', { n: e.row })}: {t(`payroll.import.err.${e.code}`)}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        )}
        <FormFooter error={run.isError ? errorText(t, run.error) : null}>
          <Button variant="outline" onClick={() => navigate('/payroll/items')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" variant="outline" disabled={run.isPending || csv.trim().length < 3}>
            {t('payroll.import.check')}
          </Button>
          <Button disabled={run.isPending || !checked?.ok} onClick={() => run.mutate(false)}>
            {t('payroll.import.apply', { count: checked?.valid ?? 0 })}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
