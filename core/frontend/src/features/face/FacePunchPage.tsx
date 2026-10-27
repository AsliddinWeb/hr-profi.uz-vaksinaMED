import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, FileWarning } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { useConfirm } from '../../components/ui/confirmContext'
import { api } from '../../lib/api'
import { fmtTime, type MeData } from '../attendance/api'
import { getPosition } from '../attendance/geo'
import { Camera, type CameraHandle } from './Camera'
import { GuidedCapture } from './GuidedCapture'
import type { FacePunchResult } from './api'
import { useFaceSession } from './useFaceSession'

/** /face/punch: Face ID bilan keldi/ketdi. Joylashuv (geofence) ham yuboriladi. */
export function FacePunchPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const confirm = useConfirm()
  const me = useQuery({ queryKey: ['attendance', 'me'], queryFn: () => api<MeData>('/api/v1/attendance/me'), retry: false })
  const open = me.data?.open_record
  const camera = useRef<CameraHandle>(null)
  const [ready, setReady] = useState(false)
  const [geoNote, setGeoNote] = useState<string | null>(null)
  const session = useFaceSession<FacePunchResult>(camera, 'verify', '/api/v1/face/punch')
  const res = session.phase === 'done' ? session.result : null
  useEffect(() => {
    if (res) void qc.invalidateQueries({ queryKey: ['attendance'] })
  }, [res, qc])

  const start = async () => {
    if (open && !(await confirm({ title: t('face.punch.confirmOutTitle'), body: t('face.punch.confirmOutBody'), confirmLabel: t('face.punch.confirmOutBtn') }))) return
    setGeoNote(null)
    const extra: Record<string, string> = {}
    try {
      const p = await getPosition()
      extra.lat = String(p.lat)
      extra.lng = String(p.lng)
      extra.accuracy = String(p.accuracy)
    } catch (e) {
      setGeoNote(t(`attendance.geo.${(e as Error).message}`))
    }
    await session.run(extra)
  }

  return (
    <div className="mx-auto flex max-w-xl flex-col gap-5">
      <PageHeader title={t('face.punch.title')} subtitle={t('face.punch.subtitle')} backTo="/attendance" backLabel={t('attendance.my.title')} />
      <Card className="flex flex-col gap-4 p-5">
        {res ? (
          <div className="flex flex-col items-center gap-3 py-8 text-center">
            <CheckCircle2 className="size-14 text-success" />
            <p className="text-lg font-semibold">{res.action === 'check_in' ? t('attendance.my.doneIn', { time: fmtTime(res.record.check_in_at) }) : t('attendance.my.doneOut', { time: fmtTime(res.record.check_out_at) })}</p>
            {res.action === 'check_in' && res.record.late_minutes > 0 && <p className="text-sm text-warning">{t('attendance.my.late', { m: res.record.late_minutes })}</p>}
            <Link to="/attendance">
              <Button variant="outline">{t('attendance.my.title')}</Button>
            </Link>
          </div>
        ) : (
          <>
            {me.data && <p className="text-sm font-medium">{open ? t('face.punch.willOut', { time: fmtTime(open.check_in_at) }) : t('face.punch.willIn')}</p>}
            <Camera ref={camera} onReady={setReady} />
            <GuidedCapture phase={session.phase} steps={session.steps} stepIndex={session.stepIndex} />
            {geoNote && <p className="text-sm text-warning">{geoNote}</p>}
            {session.error && (
              <p role="alert" className="text-sm text-danger">
                {session.error}
              </p>
            )}
            {session.error && (
              <div className="rounded-control border border-border bg-surface-2 p-4 text-sm">
                <p className="font-medium">{t('face.punch.help.title')}</p>
                <ol className="mt-2 list-decimal space-y-1 pl-5 text-muted">
                  {(['s1', 's2', 's3', 's4'] as const).map((k) => (
                    <li key={k}>{t(`face.punch.help.${k}`)}</li>
                  ))}
                </ol>
                <Link to="/attendance/issues/new?method=face" className="mt-3 flex items-center gap-2 font-medium text-primary hover:underline">
                  <FileWarning className="size-4" />
                  {t('face.punch.help.report')}
                </Link>
              </div>
            )}
            <Button className="h-12 text-base" disabled={!ready || (session.phase !== 'idle' && session.phase !== 'done')} onClick={() => void start()}>
              {t('face.punch.start')}
            </Button>
          </>
        )}
      </Card>
    </div>
  )
}
