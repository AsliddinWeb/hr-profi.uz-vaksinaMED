import { useMutation, useQueries, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, send } from '../../lib/api'
import { errorText } from '../auth/errorText'
import { Avatar } from './Avatar'
import type { Employee } from './api'

/** /employees/merge?ids=1,2: asosiy xodimni tanlab, dublikatlarni birlashtirish. */
export function MergePage() {
  const { t } = useTranslation()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const ids = (params.get('ids') ?? '').split(',').map(Number).filter((n) => Number.isInteger(n) && n > 0)
  const [primary, setPrimary] = useState<number | null>(null)

  const queries = useQueries({ queries: ids.map((id) => ({ queryKey: ['employees', 'one', id], queryFn: () => api<Employee>(`/api/v1/employees/${id}`), retry: false })) })
  const members = queries.map((q) => q.data).filter((e): e is Employee => !!e)

  const merge = useMutation({
    mutationFn: (primaryId: number) => send<Employee>('POST', '/api/v1/employees/merge', { primary_id: primaryId, secondary_ids: ids.filter((i) => i !== primaryId) }),
    onSuccess: async (e) => {
      await qc.invalidateQueries({ queryKey: ['employees'] })
      toast.push({ title: t('employees.merged'), tone: 'success' })
      navigate(`/employees/${e.id}?tab=history`, { replace: true })
    },
  })

  if (ids.length < 2) return <Navigate to="/employees/duplicates" replace />
  const loading = queries.some((q) => q.isLoading)
  // Standart asosiy: hisobi bor, bo'lmasa eng kichik raqamli (eng eski)
  const chosen = primary ?? (members.find((m) => m.user) ?? members.slice().sort((a, b) => a.employee_no - b.employee_no)[0])?.id ?? null

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <PageHeader title={t('employees.merge')} subtitle={t('employees.mergeSubtitle')} backTo="/employees/duplicates" backLabel={t('employees.duplicatesTitle')} />
      {loading && <Skeleton className="h-48" />}
      <FormSection title={t('employees.chooseMain')} description={t('employees.chooseMainHint')}>
        <div className="grid gap-3 sm:grid-cols-2">
          {members.map((m) => (
            <label
              key={m.id}
              className={'flex cursor-pointer gap-3 rounded-control border p-4 ' + (chosen === m.id ? 'border-primary bg-primary/5' : 'border-border hover:bg-surface-2')}
            >
              <input type="radio" name="primary" className="mt-1 size-4" checked={chosen === m.id} onChange={() => setPrimary(m.id)} />
              <Avatar id={m.id} name={m.full_name} hasPhoto={m.has_photo} size={40} />
              <div className="min-w-0 text-sm">
                <div className="truncate font-medium">{m.full_name}</div>
                <div className="text-xs text-muted">
                  №{m.employee_no} · {m.phone ?? '—'}
                </div>
                <div className="text-xs text-muted">{[m.department?.name, m.position?.name].filter(Boolean).join(' · ') || '—'}</div>
                {m.user && <div className="text-xs text-muted">{m.user.login}</div>}
              </div>
            </label>
          ))}
        </div>
      </FormSection>
      <Card className="p-6 text-sm text-muted">
        <p className="mb-2 font-medium text-text">{t('employees.mergeWhat')}</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>{t('employees.mergeStep1')}</li>
          <li>{t('employees.mergeStep2')}</li>
          <li>{t('employees.mergeStep3')}</li>
          <li className="text-danger">{t('employees.mergeStep4')}</li>
        </ul>
      </Card>
      <FormFooter error={merge.isError ? errorText(t, merge.error) : null}>
        <Button variant="outline" onClick={() => navigate('/employees/duplicates')}>
          {t('common.cancel')}
        </Button>
        <Button
          disabled={chosen === null || merge.isPending || members.length < 2}
          onClick={async () => {
            if (chosen !== null && (await confirm({ title: t('employees.merge'), body: t('employees.mergeConfirm'), danger: true, confirmLabel: t('employees.merge') }))) merge.mutate(chosen)
          }}
        >
          {t('employees.merge')}
        </Button>
      </FormFooter>
    </div>
  )
}
