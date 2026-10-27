import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ScanFace, ShieldCheck, Trash2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { errorText } from '../auth/errorText'
import type { FaceStatus } from './api'

/** /face: xodimning o'z Face ID holati: rozilik, ro'yxatdan o'tish, tekshirish, ma'lumotni o'chirish. */
export function MyFacePage() {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const status = useQuery({ queryKey: ['face', 'status'], queryFn: () => api<FaceStatus>('/api/v1/face/status'), retry: false })
  const revoke = useMutation({
    mutationFn: () => send('DELETE', '/api/v1/face/consent'),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['face'] })
      toast.push({ title: t('face.my.revoked'), tone: 'success' })
    },
  })
  const s = status.data

  if (status.error instanceof ApiError) {
    return (
      <div className="mx-auto max-w-2xl">
        <PageHeader title={t('face.my.title')} />
        <Card className="mt-5 p-6 text-sm text-danger" role="alert">
          {errorText(t, status.error)}
        </Card>
      </div>
    )
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <PageHeader title={t('face.my.title')} subtitle={t('face.my.subtitle')} />
      {!s ? (
        <Skeleton className="h-56" />
      ) : (
        <>
          <Card tint={s.enrolled ? 'mint' : 'lilac'} className="flex flex-col gap-4 p-6">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={s.consent.given ? 'success' : 'warning'}>{s.consent.given ? t('face.my.consentGiven') : s.consent.revoked_at ? t('face.my.consentRevoked') : s.consent.outdated ? t('face.my.consentOutdated') : t('face.my.consentNone')}</Badge>
              <Badge tone={s.enrolled ? 'success' : 'neutral'}>{s.enrolled ? t('face.my.enrolled') : t('face.my.notEnrolled')}</Badge>
            </div>
            {s.consent.given_at && s.consent.given && <p className="text-sm text-muted">{t('face.my.consentDate', { date: formatDateTime(s.consent.given_at, i18n.language), version: s.consent.version })}</p>}
            {s.enrolled && s.last_verified_at && <p className="text-sm text-muted">{t('face.my.lastVerified', { date: formatDateTime(s.last_verified_at, i18n.language) })}</p>}
            <div className="flex flex-wrap gap-3">
              {!s.consent.given && (
                <Link to="/face/consent">
                  <Button>
                    <ShieldCheck className="size-4" />
                    {t('face.my.giveConsent')}
                  </Button>
                </Link>
              )}
              {s.consent.given && (
                <Link to="/face/enroll">
                  <Button variant={s.enrolled ? 'outline' : 'primary'}>
                    <ScanFace className="size-4" />
                    {s.enrolled ? t('face.my.reEnroll') : t('face.my.enroll')}
                  </Button>
                </Link>
              )}
              {s.enrolled && (
                <Link to="/face/punch">
                  <Button>
                    <ScanFace className="size-4" />
                    {t('face.my.punch')}
                  </Button>
                </Link>
              )}
            </div>
          </Card>

          <Card className="flex flex-col gap-3 p-6 text-sm">
            <h2 className="font-semibold">{t('face.my.privacyTitle')}</h2>
            <ul className="list-disc space-y-1.5 pl-5 text-muted">
              <li>{t('face.my.privacy1')}</li>
              <li>{t('face.my.privacy2')}</li>
              <li>{t('face.my.privacy3', { days: s.retention_days })}</li>
              <li>{t('face.my.privacy4')}</li>
            </ul>
            {(s.consent.given || s.enrolled) && (
              <div>
                <Button
                  variant="outline"
                  className="text-danger"
                  disabled={revoke.isPending}
                  onClick={async () => {
                    if (await confirm({ title: t('face.my.revoke'), body: t('face.my.revokeConfirm'), danger: true, confirmLabel: t('face.my.revoke') })) revoke.mutate()
                  }}
                >
                  <Trash2 className="size-4" />
                  {t('face.my.revoke')}
                </Button>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
