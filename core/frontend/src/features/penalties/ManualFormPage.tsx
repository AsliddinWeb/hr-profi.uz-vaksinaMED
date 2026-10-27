import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { useToast } from '../../components/ui/toastContext'
import { api, send } from '../../lib/api'
import { todayLocal } from '../attendance/api'
import { errorText, fieldErrors } from '../auth/errorText'
import { EmployeePicker, type PickedEmployee } from '../letters/EmployeePicker'
import { money, TYPES, type Penalty, type RulesOverview } from './api'

/** /penalties/new: qo'lda jarima/chora (tasdiq kutadi). */
export function ManualFormPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [today] = useState(todayLocal)
  const rules = useQuery({ queryKey: ['penalties', 'rules'], queryFn: () => api<RulesOverview>('/api/v1/penalties/rules') })
  const [employee, setEmployee] = useState<PickedEmployee | null>(null)
  const [type, setType] = useState<string>('discipline')
  const [date, setDate] = useState(today)
  const [step, setStep] = useState('')
  const [amount, setAmount] = useState('')
  const [block, setBlock] = useState('')
  const [label, setLabel] = useState('')
  const [reason, setReason] = useState('')
  const steps = rules.data?.current?.config.steps ?? []

  const save = useMutation({
    mutationFn: () =>
      send<Penalty>('POST', '/api/v1/penalties', {
        employee_id: employee?.id, incident_type: type, incident_date: date, step: step ? Number(step) : null,
        amount: amount !== '' ? Number(amount) : null, block_days: block !== '' ? Number(block) : null, label: label || null, reason,
      }), // fmt: skip
    onSuccess: (p) => {
      void qc.invalidateQueries({ queryKey: ['penalties'] })
      toast.push({ title: t('penalties.created'), tone: 'success' })
      navigate(`/penalties/${p.id}`, { replace: true })
    },
  })
  const fe = save.isError ? fieldErrors(t, save.error) : {}
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={t('penalties.add')} subtitle={t('penalties.manualHint')} backTo="/penalties" backLabel={t('penalties.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('penalties.form.who')}>
          <Field label={t('employees.fullName')}>{(id) => <EmployeePicker id={id} value={employee} onChange={setEmployee} />}</Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('penalties.violation')}>
              {(id) => (
                <Select id={id} value={type} onChange={(e) => setType(e.target.value)}>
                  {TYPES.map((k) => (
                    <option key={k} value={k}>
                      {t(`letters.incidents.${k}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('letters.form.incidentDate')} error={fe.incident_date}>
              {(id) => <Input id={id} type="date" value={date} max={today} onChange={(e) => setDate(e.target.value)} required />}
            </Field>
          </div>
        </FormSection>
        <FormSection title={t('penalties.form.measure')} description={t('penalties.form.measureHint')}>
          <Field label={t('penalties.form.fromStep')}>
            {(id) => (
              <Select id={id} value={step} onChange={(e) => setStep(e.target.value)}>
                <option value="">{t('penalties.form.custom')}</option>
                {steps.map((s) => (
                  <option key={s.step} value={s.step}>
                    {t('penalties.stepN', { n: s.step })}: {s.label} {s.amount > 0 ? `(${money(s.amount)})` : ''}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={t('penalties.amount')} hint={t('penalties.form.overrideHint')}>
              {(id) => <Input id={id} type="number" min={0} step="1000" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder={step ? String(steps[Number(step) - 1]?.amount ?? 0) : '0'} />}
            </Field>
            <Field label={t('penalties.block')}>{(id) => <Input id={id} type="number" min={0} max={90} value={block} onChange={(e) => setBlock(e.target.value)} placeholder={step ? String(steps[Number(step) - 1]?.block_days ?? 0) : '0'} />}</Field>
            <Field label={t('penalties.form.label')}>{(id) => <Input id={id} value={label} onChange={(e) => setLabel(e.target.value)} maxLength={120} placeholder={t('penalties.form.labelPlaceholder')} />}</Field>
          </div>
        </FormSection>
        <FormSection title={t('attendance.record.reason')}>
          <Field label={t('attendance.record.reason')} error={fe.reason}>
            {(id) => <textarea id={id} value={reason} onChange={(e) => setReason(e.target.value)} rows={4} maxLength={2000} required minLength={3} className="w-full rounded-control border border-border bg-surface px-3 py-2 text-sm" />}
          </Field>
        </FormSection>
        <FormFooter error={save.isError && !Object.keys(fe).length ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate('/penalties')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !employee || reason.trim().length < 3}>
            {t('penalties.form.submit')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
