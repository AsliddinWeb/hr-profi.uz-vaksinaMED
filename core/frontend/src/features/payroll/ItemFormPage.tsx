import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { EmployeePicker, type Picked } from './EmployeePicker'
import { currentPeriod, KINDS, type Item } from './api'

/** /payroll/items/new va /payroll/items/:id/edit */
export function ItemFormPage() {
  const { id } = useParams()
  const iid = id ? Number(id) : null
  const q = useQuery({ queryKey: ['payroll', 'item', iid], queryFn: () => api<Item>(`/api/v1/payroll/items/${iid}`), enabled: iid !== null, retry: false })
  if (iid === null) return <ItemForm it={null} />
  if (q.isLoading) return <Skeleton className="mx-auto h-72 max-w-3xl" />
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!q.data) return null
  return <ItemForm key={q.data.id} it={q.data} />
}

function ItemForm({ it }: { it: Item | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const [sp] = useSearchParams()
  const [emp, setEmp] = useState<Picked | null>(it ? { id: it.employee.id, name: it.employee.name ?? '' } : null)
  const [period, setPeriod] = useState(it?.period ?? sp.get('period') ?? currentPeriod())
  const [kind, setKind] = useState<string>(it?.kind ?? 'sales')
  const [amount, setAmount] = useState(it ? String(it.amount) : '')
  const [note, setNote] = useState(it?.note ?? '')
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const back = `/payroll/items`
  const save = useMutation({
    mutationFn: () => {
      const body = { employee_id: emp?.id, period, kind, amount: Number(amount), note: note || null }
      return it ? send<Item>('PUT', `/api/v1/payroll/items/${it.id}`, body) : send<Item>('POST', '/api/v1/payroll/items', body)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['payroll'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(back, { replace: true })
    },
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/payroll/items/${it?.id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['payroll'] })
      toast.push({ title: t('payroll.item.deleted'), tone: 'success' })
      navigate(back, { replace: true })
    },
    onError: (e) => setDeleteError(errorText(t, e)),
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={it ? t('payroll.item.edit') : t('payroll.item.add')} backTo={back} backLabel={t('payroll.tabs.items')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('payroll.item.what')}>
          <Field label={t('payroll.line.employee')}>{(id) => <EmployeePicker id={id} value={emp} onChange={setEmp} disabled={!!it} />}</Field>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={t('payroll.run.period')}>{(id) => <Input id={id} type="month" value={period} onChange={(e) => setPeriod(e.target.value)} required />}</Field>
            <Field label={t('payroll.item.kind')}>
              {(id) => (
                <Select id={id} value={kind} onChange={(e) => setKind(e.target.value)}>
                  {KINDS.map((k) => (
                    <option key={k} value={k}>
                      {t(`payroll.kind.${k}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={kind === 'kpi' ? t('payroll.item.kpiScore') : t('payroll.item.amount')} hint={t(`payroll.kindHint.${kind}`)}>{(id) => <Input id={id} type="number" min={0} max={kind === 'kpi' ? 100 : undefined} step="any" value={amount} onChange={(e) => setAmount(e.target.value)} required />}</Field>
          </div>
          <Field label={t('recruit.candidate.note')}>{(id) => <Input id={id} value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} />}</Field>
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(back)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !emp || amount === ''}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
      {it && (
        <FormSection title={t('org.dangerZone')} danger>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              className="text-danger"
              disabled={remove.isPending}
              onClick={async () => {
                if (await confirm({ title: t('payroll.item.delete'), body: `${it.employee.name} · ${t(`payroll.kind.${it.kind}`)}`, danger: true, confirmLabel: t('common.delete') })) {
                  setDeleteError(null)
                  remove.mutate()
                }
              }}
            >
              <Trash2 className="size-4" />
              {t('payroll.item.delete')}
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
