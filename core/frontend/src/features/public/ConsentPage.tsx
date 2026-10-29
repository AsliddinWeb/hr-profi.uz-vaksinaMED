import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, ShieldCheck } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'

import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { api, ApiError, send } from '../../lib/api'

/** /consent/:token: nomzod fon tekshiruviga «Roziman» deydi (kirish shart emas). */
export function BackgroundConsentPage() {
  const { t } = useTranslation()
  const token = useParams().token ?? ''
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['public-consent', token], queryFn: () => api<{ name: string | null; consent_at: string | null }>(`/api/v1/public/consent/${token}`), retry: false })
  const agree = useMutation({ mutationFn: () => send('POST', `/api/v1/public/consent/${token}/agree`), onSuccess: () => void qc.invalidateQueries({ queryKey: ['public-consent', token] }) })
  if (q.error instanceof ApiError) {
    return (
      <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-4 py-10">
        <Card className="p-8 text-center" role="alert">
          <p className="font-semibold">{t('recruitCore.public.notFound')}</p>
        </Card>
      </main>
    )
  }
  const d = q.data
  if (!d) return <main className="mx-auto max-w-lg px-4 py-10"><Card className="h-40 animate-pulse" /></main>
  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center gap-4 px-4 py-10">
      <Card className="flex flex-col gap-4 p-6">
        <div className="flex items-center gap-3">
          <ShieldCheck className="size-8 text-primary" />
          <h1 className="text-xl font-semibold">{t('recruitEval.public.consentTitle')}</h1>
        </div>
        <p className="text-sm">{t('recruitEval.public.consentText', { name: d.name ?? '' })}</p>
        <ul className="list-disc pl-5 text-sm text-muted">
          {['reference', 'documents', 'social', 'other'].map((k) => (
            <li key={k}>{t(`recruitEval.bg.items.${k}`)}</li>
          ))}
        </ul>
        {d.consent_at ? (
          <div className="flex items-center gap-2 text-success">
            <CheckCircle2 className="size-5" />
            {t('recruitEval.public.consentDone')}
          </div>
        ) : (
          <div>
            <Button disabled={agree.isPending} onClick={() => agree.mutate()}>
              {t('recruitEval.public.agree')}
            </Button>
          </div>
        )}
      </Card>
    </main>
  )
}
