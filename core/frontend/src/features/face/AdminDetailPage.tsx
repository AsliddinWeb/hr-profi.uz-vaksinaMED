import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { FormSection } from '../../components/ui/Form'
import { Field, Input } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import type { FaceDetail } from './api'

/** /face/admin/:id: xodimning Face ID holati, urinishlar tarixi. Ochilishi auditga yoziladi. Shablonni o'chirish sabab bilan. */
export function AdminDetailPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const manage = useCan()('face.manage')
  const [reason, setReason] = useState('')
  const data = useQuery({ queryKey: ['face', 'detail', id], queryFn: () => api<FaceDetail>(`/api/v1/face/employees/${id}`), retry: false, staleTime: 0, gcTime: 0 })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/face/employees/${id}/templates?reason=${encodeURIComponent(reason)}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['face'] })
      toast.push({ title: t('face.admin.deleted'), tone: 'success' })
      navigate('/face/admin')
    },
  })
  if (data.error instanceof ApiError && data.error.status === 404) return <NotFound />
  const d = data.data
  if (!d) return <Skeleton className="mx-auto h-96 max-w-3xl" />

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <PageHeader title={d.employee.full_name} subtitle={t('face.admin.detailSubtitle')} backTo="/face/admin" backLabel={t('face.admin.title')} />
      <Card className="flex flex-wrap gap-2 p-5">
        <Badge tone={d.state === 'enrolled' ? 'success' : d.state === 'revoked' ? 'danger' : 'neutral'}>{t(`face.state.${d.state}`)}</Badge>
        <Badge>{t('face.admin.verifyOk', { count: d.verify_ok })}</Badge>
        <Badge tone={d.verify_fail ? 'warning' : 'neutral'}>{t('face.admin.verifyFail', { count: d.verify_fail })}</Badge>
        {d.consent && <Badge>{t('face.consent.version', { version: d.consent.version })}</Badge>}
      </Card>
      <p className="text-xs text-muted">{t('face.admin.privacyNote')}</p>

      <Card className="overflow-hidden">
        <h2 className="px-5 pt-5 font-semibold">{t('face.admin.templates')}</h2>
        <div className="overflow-x-auto">
          <table className="mt-3 w-full text-left text-sm">
            <thead className="border-y border-border text-xs text-muted">
              <tr>
                <th className="px-5 py-2.5 font-medium">{t('face.admin.pose')}</th>
                <th className="px-5 py-2.5 font-medium">{t('face.admin.quality')}</th>
                <th className="px-5 py-2.5 font-medium">{t('face.admin.created')}</th>
                <th className="hidden px-5 py-2.5 font-medium sm:table-cell">{t('face.admin.lastVerified')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {d.templates.map((tp) => (
                <tr key={tp.id}>
                  <td className="px-5 py-2.5">{t(`face.pose.${tp.pose}`)}</td>
                  <td className="px-5 py-2.5 tabular-nums">{tp.quality}</td>
                  <td className="px-5 py-2.5 text-muted">{formatDateTime(tp.created_at, i18n.language)}</td>
                  <td className="hidden px-5 py-2.5 text-muted sm:table-cell">{tp.last_verified_at ? formatDateTime(tp.last_verified_at, i18n.language) : '—'}</td>
                </tr>
              ))}
              {d.templates.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-5 py-6 text-center text-muted">
                    {t('common.empty')}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <Card className="overflow-hidden">
        <h2 className="px-5 pt-5 font-semibold">{t('face.admin.attempts')}</h2>
        <ul className="mt-3 divide-y divide-border text-sm">
          {d.attempts.map((a) => (
            <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 px-5 py-2.5">
              <span className="flex items-center gap-2">
                <Badge tone={a.success ? 'success' : 'danger'}>{a.success ? t('face.admin.ok') : t('face.admin.fail')}</Badge>
                {t(`face.admin.purpose.${a.purpose}`)}
                {a.reason && <span className="text-muted">· {t(`face.admin.reason.${a.reason}`, { defaultValue: a.reason })}</span>}
              </span>
              <span className="text-xs text-muted">{formatDateTime(a.created_at, i18n.language)}</span>
            </li>
          ))}
          {d.attempts.length === 0 && <li className="px-5 py-6 text-center text-muted">{t('common.empty')}</li>}
        </ul>
      </Card>

      {manage && d.templates.length > 0 && (
        <FormSection title={t('org.dangerZone')} description={t('face.admin.deleteHint')} danger>
          <Field label={t('attendance.record.reason')}>{(fid) => <Input id={fid} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} placeholder={t('face.admin.reasonPlaceholder')} />}</Field>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              className="text-danger"
              disabled={remove.isPending || reason.trim().length < 3}
              onClick={async () => {
                if (await confirm({ title: t('face.admin.delete'), body: t('face.admin.deleteConfirm', { name: d.employee.full_name }), danger: true, confirmLabel: t('common.delete') })) remove.mutate()
              }}
            >
              <Trash2 className="size-4" />
              {t('face.admin.delete')}
            </Button>
            {remove.isError && (
              <span role="alert" className="text-sm text-danger">
                {errorText(t, remove.error)}
              </span>
            )}
          </div>
        </FormSection>
      )}
    </div>
  )
}
