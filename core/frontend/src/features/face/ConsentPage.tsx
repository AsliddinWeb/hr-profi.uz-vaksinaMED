import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, send } from '../../lib/api'
import { errorText } from '../auth/errorText'
import type { FaceStatus } from './api'

/** /face/consent: biometrik ma'lumotga rozilik (matn versiyasi serverdagi joriy versiya bilan mos bo'lishi shart). */
export function ConsentPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [agree, setAgree] = useState(false)
  const status = useQuery({ queryKey: ['face', 'status'], queryFn: () => api<FaceStatus>('/api/v1/face/status'), retry: false })
  const give = useMutation({
    mutationFn: () => send('POST', '/api/v1/face/consent', { version: status.data?.current_version }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['face'] })
      toast.push({ title: t('face.consent.saved'), tone: 'success' })
      navigate('/face/enroll')
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (agree) give.mutate()
  }
  if (!status.data) return <Skeleton className="mx-auto h-96 max-w-3xl" />

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={t('face.consent.title')} subtitle={t('face.consent.version', { version: status.data.current_version })} backTo="/face" backLabel={t('face.my.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('face.consent.whatTitle')}>
          <ol className="list-decimal space-y-2.5 pl-5 text-sm">
            {[1, 2, 3, 4, 5, 6].map((n) => (
              <li key={n}>{t(`face.consent.p${n}`, { days: status.data?.retention_days })}</li>
            ))}
          </ol>
        </FormSection>
        <FormSection title={t('face.consent.confirmTitle')}>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" className="mt-0.5 size-4" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
            <span>{t('face.consent.agree')}</span>
          </label>
        </FormSection>
        <FormFooter error={give.isError ? errorText(t, give.error) : null}>
          <Button variant="outline" onClick={() => navigate('/face')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={!agree || give.isPending}>
            {t('face.consent.accept')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
