import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { todayLocal } from '../attendance/api'
import { errorText } from '../auth/errorText'
import { EmployeePicker, type Picked } from './EmployeePicker'
import type { Scheme } from './api'

const LIST = '/payroll/schemes'

/** /payroll/schemes/new va /payroll/schemes/:id/edit */
export function SchemeFormPage() {
  const { id } = useParams()
  const sid = id ? Number(id) : null
  const q = useQuery({ queryKey: ['payroll', 'scheme', sid], queryFn: () => api<Scheme>(`/api/v1/payroll/schemes/${sid}`), enabled: sid !== null, retry: false })
  if (sid === null) return <SchemeForm s={null} />
  if (q.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!q.data) return null
  return <SchemeForm key={q.data.id} s={q.data} />
}

function SchemeForm({ s }: { s: Scheme | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const [sp] = useSearchParams()
  const [emp, setEmp] = useState<Picked | null>(s ? { id: s.employee.id, name: s.employee.name ?? '' } : sp.get('employee_id') ? { id: Number(sp.get('employee_id')), name: sp.get('name') ?? '' } : null)
  const [from, setFrom] = useState(s?.effective_from ?? todayLocal().slice(0, 8) + '01')
  const [fixed, setFixed] = useState(String(s?.fixed_amount ?? ''))
  const [pct, setPct] = useState(String(s?.commission_percent ?? 0))
  const [planBonus, setPlanBonus] = useState(String(s?.plan_bonus ?? 0))
  const [kpi, setKpi] = useState(String(s?.kpi_amount ?? 0))
  const [note, setNote] = useState(s?.note ?? '')
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const save = useMutation({
    mutationFn: () => {
      const body = { employee_id: emp?.id, effective_from: from, fixed_amount: Number(fixed) || 0, commission_percent: Number(pct) || 0, plan_bonus: Number(planBonus) || 0, kpi_amount: Number(kpi) || 0, note: note || null }
      return s ? send<Scheme>('PUT', `/api/v1/payroll/schemes/${s.id}`, body) : send<Scheme>('POST', '/api/v1/payroll/schemes', body)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['payroll'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(LIST, { replace: true })
    },
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/payroll/schemes/${s?.id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['payroll'] })
      toast.push({ title: t('payroll.scheme.deleted'), tone: 'success' })
      navigate(LIST, { replace: true })
    },
    onError: (e) => setDeleteError(errorText(t, e)),
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  const num = (v: string, set: (s: string) => void, lbl: string, hint?: string, step?: string) => (
    <Field label={lbl} hint={hint}>{(id) => <Input id={id} type="number" min={0} step={step} value={v} onChange={(e) => set(e.target.value)} />}</Field>
  )
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={s ? t('payroll.scheme.edit') : t('payroll.scheme.add')} subtitle={s?.employee.name ?? undefined} backTo={LIST} backLabel={t('payroll.tabs.schemes')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('payroll.scheme.who')}>
          <Field label={t('payroll.line.employee')}>{(id) => <EmployeePicker id={id} value={emp} onChange={setEmp} disabled={!!s} />}</Field>
          <Field label={t('payroll.scheme.from')} hint={t('payroll.scheme.fromHint')}>{(id) => <Input id={id} type="date" value={from} onChange={(e) => setFrom(e.target.value)} required />}</Field>
        </FormSection>
        <FormSection title={t('payroll.scheme.amounts')}>
          {num(fixed, setFixed, t('payroll.scheme.fixed'), t('payroll.scheme.fixedHint'))}
          <div className="grid gap-4 sm:grid-cols-3">
            {num(pct, setPct, t('payroll.scheme.commission'), t('payroll.scheme.commissionHint'), '0.001')}
            {num(planBonus, setPlanBonus, t('payroll.scheme.planBonus'), t('payroll.scheme.planBonusHint'))}
            {num(kpi, setKpi, t('payroll.scheme.kpi'), t('payroll.scheme.kpiHint'))}
          </div>
          <Field label={t('recruit.candidate.note')}>{(id) => <Input id={id} value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} />}</Field>
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(LIST)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !emp}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
      {s && (
        <FormSection title={t('org.dangerZone')} description={t('payroll.scheme.deleteHint')} danger>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              className="text-danger"
              disabled={remove.isPending}
              onClick={async () => {
                if (await confirm({ title: t('payroll.scheme.delete'), body: s.employee.name ?? '', danger: true, confirmLabel: t('common.delete') })) {
                  setDeleteError(null)
                  remove.mutate()
                }
              }}
            >
              <Trash2 className="size-4" />
              {t('payroll.scheme.delete')}
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
