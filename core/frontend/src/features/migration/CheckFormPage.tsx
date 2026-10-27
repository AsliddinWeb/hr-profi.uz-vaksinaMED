import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText, fieldErrors } from '../auth/errorText'
import { METRICS, type Check } from './api'

const LIST = '/migration/reconcile'

/** /migration/checks/new va /migration/checks/:id/edit */
export function CheckFormPage() {
  const { id } = useParams()
  const cid = id ? Number(id) : null
  const q = useQuery({ queryKey: ['migration', 'check', cid], queryFn: () => api<Check>(`/api/v1/migration/checks/${cid}`), enabled: cid !== null, retry: false })
  if (cid === null) return <CheckForm c={null} />
  if (q.isLoading) return <Skeleton className="mx-auto h-72 max-w-3xl" />
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!q.data) return null
  return <CheckForm key={q.data.id} c={q.data} />
}

function CheckForm({ c }: { c: Check | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const [label, setLabel] = useState(c?.label ?? '')
  const [metric, setMetric] = useState<string>(c?.metric ?? 'employees_total')
  const [period, setPeriod] = useState(c?.period ?? '')
  const [branchId, setBranchId] = useState(String(c?.branch_id ?? ''))
  const [expected, setExpected] = useState(String(c?.expected ?? ''))
  const [tolerance, setTolerance] = useState(String(c?.tolerance ?? 0))
  const [note, setNote] = useState(c?.note ?? '')
  const branches = useQuery({ queryKey: ['migration', 'branches'], queryFn: () => api<{ id: number; name: string }[]>('/api/v1/reception/branches') })
  const att = metric.startsWith('attendance')
  const save = useMutation({
    mutationFn: () => {
      const body = { label, metric, period: att ? period : null, branch_id: branchId ? Number(branchId) : null, expected: Number(expected), tolerance: Number(tolerance) || 0, note: note || null }
      return c ? send('PUT', `/api/v1/migration/checks/${c.id}`, body) : send('POST', '/api/v1/migration/checks', body)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['migration'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(LIST)
    },
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/migration/checks/${c?.id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['migration'] })
      navigate(LIST)
    },
  })
  const fe = save.isError ? fieldErrors(t, save.error) : {}
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={c ? t('migration.check.edit') : t('migration.addCheck')} subtitle={c?.label} backTo={LIST} backLabel={t('migration.tabs.reconcile')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('migration.check.section')} description={t('migration.check.hint')}>
          <Field label={t('migration.check.label')} error={fe.label}>{(id) => <Input id={id} value={label} onChange={(e) => setLabel(e.target.value)} required maxLength={160} autoFocus />}</Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('migration.check.metric')}>
              {(id) => (
                <Select id={id} value={metric} onChange={(e) => setMetric(e.target.value)}>
                  {METRICS.map((m) => (
                    <option key={m} value={m}>
                      {t(`migration.metric.${m}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            {att && <Field label={t('migration.check.period')} hint="YYYY-MM" error={fe.period}>{(id) => <Input id={id} type="month" value={period} onChange={(e) => setPeriod(e.target.value)} required />}</Field>}
            <Field label={t('migration.check.branch')}>
              {(id) => (
                <Select id={id} value={branchId} onChange={(e) => setBranchId(e.target.value)}>
                  <option value="">{t('migration.check.allBranches')}</option>
                  {branches.data?.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('migration.check.expected')} hint={metric === 'attendance_hours' ? t('migration.check.hoursHint') : undefined} error={fe.expected}>{(id) => <Input id={id} type="number" step="0.01" min={0} value={expected} onChange={(e) => setExpected(e.target.value)} required />}</Field>
            <Field label={t('migration.check.tolerance')} hint={t('migration.check.toleranceHint')}>{(id) => <Input id={id} type="number" step="0.01" min={0} value={tolerance} onChange={(e) => setTolerance(e.target.value)} />}</Field>
          </div>
          <Field label={t('migration.check.note')}>{(id) => <Input id={id} value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} />}</Field>
        </FormSection>
        <FormFooter error={save.isError && !Object.keys(fe).length ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(LIST)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !label.trim() || expected === '' || (att && !period)}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
      {c && (
        <FormSection title={t('org.dangerZone')} danger>
          <Button
            variant="outline"
            className="w-fit text-danger"
            disabled={remove.isPending}
            onClick={async () => {
              if (await confirm({ title: t('migration.check.delete'), body: c.label, danger: true, confirmLabel: t('common.delete') })) remove.mutate()
            }}
          >
            <Trash2 className="size-4" />
            {t('migration.check.delete')}
          </Button>
        </FormSection>
      )}
    </div>
  )
}
