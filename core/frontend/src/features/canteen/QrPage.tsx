import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Printer, RefreshCw, Settings } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { api, send } from '../../lib/api'
import { errorText } from '../auth/errorText'

/** /canteen/qr: abet uchun chop etiladigan QR kod (o'zgarmas; almashtirilsa eskisi ishlamaydi). */
export function QrPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const confirm = useConfirm()
  const q = useQuery({ queryKey: ['canteen', 'qr'], queryFn: () => api<{ url: string; svg: string; epoch: number }>('/api/v1/canteen/qr') })
  const rotate = useMutation({ mutationFn: () => send('POST', '/api/v1/canteen/qr/rotate'), onSuccess: () => void qc.invalidateQueries({ queryKey: ['canteen'] }) })
  return (
    <div className="mx-auto flex max-w-xl flex-col gap-5">
      <PageHeader
        title={t('canteen.qr.title')}
        subtitle={t('canteen.qr.subtitle')}
        actions={
          <Link to="/canteen/settings">
            <Button variant="outline">
              <Settings className="size-4" />
              {t('canteen.settings.title')}
            </Button>
          </Link>
        }
      />
      {!q.data ? (
        <Skeleton className="h-96" />
      ) : (
        <Card className="flex flex-col items-center gap-4 p-8 print:shadow-none">
          <div className="w-full max-w-72 rounded-card bg-white p-3 [&>svg]:h-auto [&>svg]:w-full" dangerouslySetInnerHTML={{ __html: q.data.svg }} aria-label={t('canteen.qr.title')} role="img" />
          <p className="text-center text-sm font-medium">{t('canteen.qr.scan')}</p>
          <p className="break-all text-center text-xs text-muted">{q.data.url}</p>
          <div className="flex flex-wrap justify-center gap-2 print:hidden">
            <Button onClick={() => window.print()}>
              <Printer className="size-4" />
              {t('canteen.qr.print')}
            </Button>
            <Button
              variant="outline"
              disabled={rotate.isPending}
              onClick={async () => {
                if (await confirm({ title: t('canteen.qr.rotate'), body: t('canteen.qr.rotateHint'), danger: true, confirmLabel: t('canteen.qr.rotate') })) rotate.mutate()
              }}
            >
              <RefreshCw className="size-4" />
              {t('canteen.qr.rotate')}
            </Button>
          </div>
          {rotate.isError && (
            <p role="alert" className="text-sm text-danger">
              {errorText(t, rotate.error)}
            </p>
          )}
        </Card>
      )}
    </div>
  )
}
