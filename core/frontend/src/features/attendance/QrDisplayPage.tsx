import { useMutation, useQuery } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Select } from '../../components/ui/Input'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, send } from '../../lib/api'
import type { BranchPage } from '../branches/api'
import { errorText } from '../auth/errorText'
import type { QrData } from './api'

/** /attendance/qr: filialdagi ekranda ko'rsatiladigan, har daqiqa yangilanadigan QR kod. */
export function QrDisplayPage() {
  const { t } = useTranslation()
  const confirm = useConfirm()
  const toast = useToast()
  const [branchId, setBranchId] = useState('')
  const branches = useQuery({ queryKey: ['branches', 'select'], queryFn: () => api<BranchPage>('/api/v1/branches?size=200') })
  const qr = useQuery({
    queryKey: ['attendance', 'qr', branchId],
    queryFn: () => api<QrData>(`/api/v1/attendance/branches/${branchId}/qr`),
    enabled: !!branchId,
    refetchInterval: 20_000,
    refetchIntervalInBackground: true,
  })
  const rotate = useMutation({
    mutationFn: () => send('POST', `/api/v1/attendance/branches/${branchId}/qr/rotate`),
    onSuccess: () => {
      toast.push({ title: t('attendance.qr.rotated'), tone: 'success' })
      void qr.refetch()
    },
  })

  return (
    <div className="mx-auto flex max-w-xl flex-col gap-5">
      <PageHeader title={t('attendance.qr.title')} subtitle={t('attendance.qr.subtitle')} />
      <Card className="flex flex-wrap items-center gap-3 p-4">
        <Select className="min-w-60 flex-1" value={branchId} onChange={(e) => setBranchId(e.target.value)} aria-label={t('employees.branch')}>
          <option value="">{t('attendance.qr.chooseBranch')}</option>
          {branches.data?.items
            .filter((b) => b.is_active)
            .map((b) => (
              <option key={b.id} value={b.id}>
                {b.number ? `№${b.number} · ` : ''}
                {b.name}
              </option>
            ))}
        </Select>
        {branchId && (
          <Button
            variant="outline"
            disabled={rotate.isPending}
            onClick={async () => {
              if (await confirm({ title: t('attendance.qr.rotate'), body: t('attendance.qr.rotateHint'), danger: true, confirmLabel: t('attendance.qr.rotate') })) rotate.mutate()
            }}
          >
            <RefreshCw className="size-4" />
            {t('attendance.qr.rotate')}
          </Button>
        )}
      </Card>
      {rotate.isError && <p role="alert" className="text-sm text-danger">{errorText(t, rotate.error)}</p>}
      {qr.data && (
        <Card className="flex flex-col items-center gap-4 p-8">
          <h2 className="text-lg font-semibold">{qr.data.branch.number ? `№${qr.data.branch.number} · ` : ''}{qr.data.branch.name}</h2>
          <div className="w-full max-w-sm rounded-card bg-white p-4 [&>svg]:h-auto [&>svg]:w-full" dangerouslySetInnerHTML={{ __html: qr.data.svg }} aria-label="QR" role="img" />
          <p className="text-center text-sm text-muted">{t('attendance.qr.scanHint')}</p>
          {!qr.data.branch.has_geo && <p className="text-center text-sm text-warning">{t('attendance.qr.noGeo')}</p>}
        </Card>
      )}
    </div>
  )
}
