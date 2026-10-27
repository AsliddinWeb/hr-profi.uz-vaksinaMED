import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { EmployeePicker, type Picked } from '../payroll/EmployeePicker'
import type { Driver } from './api'

const LIST = '/logistics/drivers'

/** /logistics/drivers/new va /logistics/drivers/:eid/edit */
export function DriverFormPage() {
  const { eid } = useParams()
  const id = eid ? Number(eid) : null
  const q = useQuery({ queryKey: ['logistics', 'driver', id], queryFn: () => api<Driver>(`/api/v1/logistics/drivers/${id}`), enabled: id !== null, retry: false })
  if (id === null) return <DriverForm d={null} />
  if (q.isLoading) return <Skeleton className="mx-auto h-72 max-w-3xl" />
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!q.data) return null
  return <DriverForm key={q.data.employee.id} d={q.data} />
}

function DriverForm({ d }: { d: Driver | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const [emp, setEmp] = useState<Picked | null>(d ? { id: d.employee.id, name: d.employee.name } : null)
  const [license, setLicense] = useState(d?.license_no ?? '')
  const [cats, setCats] = useState(d?.categories ?? '')
  const [expires, setExpires] = useState(d?.license_expires ?? '')
  const [note, setNote] = useState(d?.note ?? '')
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const save = useMutation({
    mutationFn: () => send('PUT', `/api/v1/logistics/drivers/${emp?.id}`, { license_no: license || null, categories: cats || null, license_expires: expires || null, note: note || null }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['logistics'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(LIST, { replace: true })
    },
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/logistics/drivers/${emp?.id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['logistics'] })
      toast.push({ title: t('logistics.driver.deleted'), tone: 'success' })
      navigate(LIST, { replace: true })
    },
    onError: (e) => setDeleteError(errorText(t, e)),
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={d?.has_profile ? t('logistics.driver.edit') : t('logistics.driver.add')} subtitle={d?.employee.name} backTo={LIST} backLabel={t('logistics.tabs.drivers')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('logistics.driver.who')} description={t('logistics.driver.whoHint')}>
          <Field label={t('logistics.driver.name')}>{(id) => <EmployeePicker id={id} value={emp} onChange={setEmp} disabled={!!d} />}</Field>
        </FormSection>
        <FormSection title={t('logistics.driver.license')}>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={t('logistics.driver.licenseNo')}>{(id) => <Input id={id} value={license} onChange={(e) => setLicense(e.target.value)} maxLength={30} />}</Field>
            <Field label={t('logistics.driver.categories')}>{(id) => <Input id={id} value={cats} onChange={(e) => setCats(e.target.value)} maxLength={30} placeholder="B, C" />}</Field>
            <Field label={t('logistics.driver.expires')} hint={t('logistics.driver.expiresHint')}>{(id) => <Input id={id} type="date" value={expires} onChange={(e) => setExpires(e.target.value)} />}</Field>
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
      {d?.has_profile && (
        <FormSection title={t('org.dangerZone')} description={t('logistics.driver.deleteHint')} danger>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              className="text-danger"
              disabled={remove.isPending}
              onClick={async () => {
                if (await confirm({ title: t('logistics.driver.delete'), body: d.employee.name, danger: true, confirmLabel: t('common.delete') })) {
                  setDeleteError(null)
                  remove.mutate()
                }
              }}
            >
              <Trash2 className="size-4" />
              {t('logistics.driver.delete')}
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
