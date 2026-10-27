import { useQueryClient } from '@tanstack/react-query'
import { CheckCircle2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Camera, type CameraHandle } from './Camera'
import { GuidedCapture } from './GuidedCapture'
import { useFaceSession } from './useFaceSession'

/** /face/enroll: kamera oldida ko'rsatmalar bo'yicha bosh burib yuzni ro'yxatdan o'tkazish. Rasm saqlanmaydi. */
export function EnrollPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const camera = useRef<CameraHandle>(null)
  const [ready, setReady] = useState(false)
  const session = useFaceSession<{ enrolled: boolean; poses: string[] }>(camera, 'enroll', '/api/v1/face/enroll')
  const done = session.phase === 'done' && session.result?.enrolled
  useEffect(() => {
    if (done) void qc.invalidateQueries({ queryKey: ['face'] })
  }, [done, qc])

  return (
    <div className="mx-auto flex max-w-xl flex-col gap-5">
      <PageHeader title={t('face.enroll.title')} subtitle={t('face.enroll.subtitle')} backTo="/face" backLabel={t('face.my.title')} />
      <Card className="flex flex-col gap-4 p-5">
        {done ? (
          <div className="flex flex-col items-center gap-3 py-8 text-center">
            <CheckCircle2 className="size-14 text-success" />
            <p className="text-lg font-semibold">{t('face.enroll.done')}</p>
            <Link to="/face/punch">
              <Button>{t('face.my.punch')}</Button>
            </Link>
          </div>
        ) : (
          <>
            <Camera ref={camera} onReady={setReady} />
            <GuidedCapture phase={session.phase} steps={session.steps} stepIndex={session.stepIndex} />
            {session.error && (
              <p role="alert" className="text-sm text-danger">
                {session.error}
              </p>
            )}
            <Button className="h-12 text-base" disabled={!ready || (session.phase !== 'idle' && session.phase !== 'done')} onClick={() => session.run()}>
              {t('face.enroll.start')}
            </Button>
            <ul className="list-disc space-y-1 pl-5 text-xs text-muted">
              <li>{t('face.enroll.tip1')}</li>
              <li>{t('face.enroll.tip2')}</li>
              <li>{t('face.enroll.tip3')}</li>
            </ul>
          </>
        )}
      </Card>
    </div>
  )
}
