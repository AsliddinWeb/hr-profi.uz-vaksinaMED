import { useQuery } from '@tanstack/react-query'
import { FileWarning, LogIn, LogOut, MapPin, QrCode, ScanFace } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { api, ApiError } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import { fmtMin, fmtTime, type MeData } from './api'
import { usePunch } from './usePunch'

/** /attendance: xodimning o'z davomati: keldi/ketdi (GPS) va oxirgi yozuvlar. */
export function MyAttendancePage() {
  const { t, i18n } = useTranslation()
  const me = useQuery({ queryKey: ['attendance', 'me'], queryFn: () => api<MeData>('/api/v1/attendance/me'), retry: false, refetchInterval: 60_000 })
  const punch = usePunch()
  const can = useCan()
  const confirm = useConfirm()
  const data = me.data
  const open = data?.open_record

  if (me.error instanceof ApiError) {
    return (
      <div className="mx-auto max-w-2xl">
        <PageHeader title={t('attendance.my.title')} />
        <Card className="mt-5 p-6 text-sm text-danger" role="alert">
          {errorText(t, me.error)}
        </Card>
      </div>
    )
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <PageHeader title={t('attendance.my.title')} subtitle={data ? `${data.employee.full_name} · ${formatDate(data.today, i18n.language)}` : undefined} />

      {!data ? (
        <Skeleton className="h-56" />
      ) : (
        <Card tint={open ? 'mint' : 'lilac'} className="flex flex-col gap-4 p-6">
          <div className="flex flex-wrap items-center gap-2">
            {data.schedule.shift ? (
              <Badge tone="success">
                {data.schedule.shift.name} · {data.schedule.shift.start_time}–{data.schedule.shift.end_time}
              </Badge>
            ) : (
              <Badge>{data.schedule.working ? t('attendance.my.noShift') : t('attendance.my.dayOff')}</Badge>
            )}
            {data.branch && <Badge>{data.branch.name}</Badge>}
          </div>
          {open ? (
            <p className="text-lg font-semibold">
              {t('attendance.my.checkedIn', { time: fmtTime(open.check_in_at) })}
              {open.late_minutes > 0 && <span className="ml-2 text-sm font-normal text-warning">{t('attendance.my.late', { m: open.late_minutes })}</span>}
            </p>
          ) : (
            <p className="text-lg font-semibold">{t('attendance.my.notCheckedIn')}</p>
          )}
          <div className="flex flex-wrap gap-3">
            <Button
              className="h-12 px-6 text-base"
              disabled={punch.isPending}
              onClick={async () => {
                if (open && !(await confirm({ title: t('attendance.my.confirmOutTitle'), body: t('attendance.my.confirmOutBody', { time: fmtTime(open.check_in_at) }), confirmLabel: t('attendance.my.confirmOutBtn') }))) return
                punch.mutate()
              }}
            >
              {open ? <LogOut className="size-5" /> : <LogIn className="size-5" />}
              {punch.isPending ? t('attendance.my.locating') : open ? t('attendance.my.checkOut') : t('attendance.my.checkIn')}
            </Button>
            {can('face.enroll') && (
              <Link to="/face/punch">
                <Button variant="outline" className="h-12 px-6 text-base">
                  <ScanFace className="size-5" />
                  {t('attendance.my.withFace')}
                </Button>
              </Link>
            )}
          </div>
          <p className="text-sm text-muted">{open ? t('attendance.my.modeOut', { time: fmtTime(open.check_in_at) }) : t('attendance.my.modeIn')}</p>
          {data.branch && !data.branch.has_geo && <p className="text-sm text-warning">{t('attendance.my.branchNoGeo')}</p>}
          {!data.branch && <p className="text-sm text-warning">{t('attendance.my.noBranch')}</p>}
          {punch.message && (
            <p role="alert" className="text-sm text-danger">
              {punch.message}
            </p>
          )}
          {punch.data && (
            <p role="status" className="text-sm font-medium text-success">
              {punch.data.action === 'check_in' ? t('attendance.my.doneIn', { time: fmtTime(punch.data.record.check_in_at) }) : t('attendance.my.doneOut', { time: fmtTime(punch.data.record.check_out_at) })}
            </p>
          )}
          <Link to="/attendance/issues/new" className="flex items-center gap-2 text-sm font-medium text-primary hover:underline">
            <FileWarning className="size-4" />
            {t('attendance.my.report')}
          </Link>
          <p className="flex items-start gap-2 text-xs text-muted">
            <QrCode className="mt-0.5 size-4 shrink-0" />
            {t('attendance.my.qrHint')}
          </p>
          <p className="flex items-start gap-2 text-xs text-muted">
            <MapPin className="mt-0.5 size-4 shrink-0" />
            {t('attendance.my.geoHint', { radius: data.branch?.radius ?? 100 })}
          </p>
        </Card>
      )}

      <Card className="overflow-hidden">
        <h2 className="px-5 pt-5 font-semibold">{t('attendance.my.recent')}</h2>
        <div className="overflow-x-auto">
          <table className="mt-3 w-full text-left text-sm">
            <thead className="border-y border-border text-xs text-muted">
              <tr>
                <th className="px-5 py-2.5 font-medium">{t('attendance.date')}</th>
                <th className="px-5 py-2.5 font-medium">{t('attendance.in')}</th>
                <th className="px-5 py-2.5 font-medium">{t('attendance.out')}</th>
                <th className="hidden px-5 py-2.5 font-medium sm:table-cell">{t('attendance.worked')}</th>
                <th className="px-5 py-2.5 font-medium" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data?.recent.map((r) => (
                <tr key={r.id}>
                  <td className="px-5 py-2.5 tabular-nums">{formatDate(r.work_date, i18n.language)}</td>
                  <td className="px-5 py-2.5 tabular-nums">{fmtTime(r.check_in_at)}</td>
                  <td className="px-5 py-2.5 tabular-nums">{fmtTime(r.check_out_at)}</td>
                  <td className="hidden px-5 py-2.5 tabular-nums sm:table-cell">{r.check_out_at ? fmtMin(r.worked_minutes) : '—'}</td>
                  <td className="px-5 py-2.5">
                    <div className="flex flex-wrap gap-1.5">
                      {r.late_minutes > 0 && <Badge tone="warning">{t('attendance.my.late', { m: r.late_minutes })}</Badge>}
                      {r.early_leave_minutes > 0 && <Badge tone="warning">{t('attendance.my.early', { m: r.early_leave_minutes })}</Badge>}
                      {r.is_manual && <Badge>{t('attendance.manual')}</Badge>}
                    </div>
                  </td>
                </tr>
              ))}
              {data && data.recent.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-center text-muted">
                    {t('common.empty')}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
