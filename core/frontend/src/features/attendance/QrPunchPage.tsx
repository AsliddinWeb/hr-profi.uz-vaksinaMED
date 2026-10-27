import { CheckCircle2, ScanLine, XCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { fmtTime } from './api'
import { usePunch } from './usePunch'

/** /attendance/punch?t=...: filial QR kodi skanerlanganda ochiladi. Natija shu sahifaning o'zida. */
export function QrPunchPage() {
  const { t } = useTranslation()
  const token = useSearchParams()[0].get('t') ?? ''
  const punch = usePunch(token)
  const done = punch.data

  return (
    <div className="mx-auto flex max-w-md flex-col gap-5">
      <PageHeader title={t('attendance.qrPunch.title')} subtitle={t('attendance.qrPunch.subtitle')} />
      <Card className="flex flex-col items-center gap-4 p-8 text-center">
        {done ? (
          <>
            <CheckCircle2 className="size-14 text-success" />
            <p className="text-lg font-semibold">
              {done.action === 'check_in' ? t('attendance.my.doneIn', { time: fmtTime(done.record.check_in_at) }) : t('attendance.my.doneOut', { time: fmtTime(done.record.check_out_at) })}
            </p>
            {done.record.late_minutes > 0 && done.action === 'check_in' && <p className="text-sm text-warning">{t('attendance.my.late', { m: done.record.late_minutes })}</p>}
            <Link to="/attendance">
              <Button variant="outline">{t('attendance.my.title')}</Button>
            </Link>
          </>
        ) : (
          <>
            {punch.message ? <XCircle className="size-14 text-danger" /> : <ScanLine className="size-14 text-primary" />}
            {!token && <p className="text-sm text-danger">{t('errors.qr_invalid')}</p>}
            {punch.message && (
              <p role="alert" className="text-sm text-danger">
                {punch.message}
              </p>
            )}
            <Button className="h-12 w-full text-base" disabled={punch.isPending || !token} onClick={() => punch.mutate()}>
              {punch.isPending ? t('attendance.my.locating') : t('attendance.qrPunch.confirm')}
            </Button>
            <p className="text-xs text-muted">{t('attendance.qrPunch.hint')}</p>
          </>
        )}
      </Card>
    </div>
  )
}
