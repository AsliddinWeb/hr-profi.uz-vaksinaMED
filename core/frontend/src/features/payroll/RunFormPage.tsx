import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input } from '../../components/ui/Input'
import { send } from '../../lib/api'
import { shiftMonth } from '../schedule/api'
import { errorText } from '../auth/errorText'
import { currentPeriod, type Run } from './api'

/** /payroll/runs/new: yangi oylik hisob-kitob (davr va soliq sozlamalari). */
export function RunFormPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [period, setPeriod] = useState(shiftMonth(currentPeriod(), -1))
  const [tax, setTax] = useState('12')
  const [inps, setInps] = useState('0.1')
  const [paidLeave, setPaidLeave] = useState(true)
  const [note, setNote] = useState('')
  const save = useMutation({
    mutationFn: () => send<Run>('POST', '/api/v1/payroll/runs', { period, tax_percent: Number(tax), inps_percent: Number(inps), paid_leave: paidLeave, note: note || null }),
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['payroll'] })
      navigate(`/payroll/runs/${r.id}`, { replace: true })
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={t('payroll.run.add')} backTo="/payroll" backLabel={t('payroll.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('payroll.run.period')}>
          <Field label={t('payroll.run.period')}>{(id) => <Input id={id} type="month" value={period} max={currentPeriod()} onChange={(e) => setPeriod(e.target.value)} required />}</Field>
          <Field label={t('recruit.candidate.note')}>{(id) => <Input id={id} value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} />}</Field>
        </FormSection>
        <FormSection title={t('payroll.run.rules')} description={t('payroll.run.rulesHint')}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('payroll.run.taxPercent')}>{(id) => <Input id={id} type="number" min={0} max={100} step="0.01" value={tax} onChange={(e) => setTax(e.target.value)} />}</Field>
            <Field label={t('payroll.run.inpsPercent')}>{(id) => <Input id={id} type="number" min={0} max={100} step="0.01" value={inps} onChange={(e) => setInps(e.target.value)} />}</Field>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4" checked={paidLeave} onChange={(e) => setPaidLeave(e.target.checked)} />
            {t('payroll.run.paidLeave')}
          </label>
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate('/payroll')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !period}>
            {t('payroll.run.create')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
