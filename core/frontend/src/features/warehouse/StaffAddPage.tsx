import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field } from '../../components/ui/Input'
import { useToast } from '../../components/ui/toastContext'
import { send } from '../../lib/api'
import { errorText } from '../auth/errorText'
import { EmployeePicker, type Picked } from '../payroll/EmployeePicker'

/** /warehouse/:id/staff/new: xodimni omborga biriktirish (xodim ish guruhi shu ombor guruhiga o'tadi). */
export function StaffAddPage() {
  const { t } = useTranslation()
  const id = Number(useParams().id)
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [emp, setEmp] = useState<Picked | null>(null)
  const back = `/warehouse/${id}`
  const save = useMutation({
    mutationFn: () => send<{ moved_from: string | null }>('POST', `/api/v1/warehouse/${id}/staff`, { employee_id: emp?.id }),
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['warehouse'] })
      toast.push({ title: r.moved_from ? t('warehouse.movedFrom', { name: r.moved_from }) : t('common.saved'), tone: 'success' })
      navigate(back, { replace: true })
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={t('warehouse.staffAdd')} backTo={back} backLabel={t('warehouse.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('payroll.line.employee')} description={t('warehouse.staffAddHint')}>
          <Field label={t('payroll.line.employee')}>{(fid) => <EmployeePicker id={fid} value={emp} onChange={setEmp} />}</Field>
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(back)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !emp}>
            {t('warehouse.staffAddBtn')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
