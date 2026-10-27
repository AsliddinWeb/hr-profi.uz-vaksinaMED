import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { api, send } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { errorText } from '../auth/errorText'

interface Row {
  employee_id: number
  name: string
  position: string | null
  branch: string | null
  hire_date: string | null
  status: 'waiting_docs' | 'waiting_order' | 'order_ready'
  docs_note: string | null
  order_no: string | null
}

/** /kadr: yangi xodimlar: hujjatlar qabul qilindi va kadr buyrug'i tayyor belgilari (xabarlar o'zi ketadi). */
export function KadrPage() {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['kadr'], queryFn: () => api<Row[]>('/api/v1/kadr'), refetchInterval: 60_000 })
  const [text, setText] = useState<Record<number, string>>({})
  const act = useMutation({
    mutationFn: ({ id, path, body }: { id: number; path: 'docs' | 'order'; body: unknown }) => send('POST', `/api/v1/kadr/${id}/${path}`, body),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['kadr'] }),
  })
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader title={t('onboarding.kadr.title')} subtitle={t('onboarding.kadr.subtitle')} />
      {!q.data ? (
        <Skeleton className="h-40" />
      ) : (
        <div className="flex flex-col gap-3">
          {q.data.map((r) => (
            <Card key={r.employee_id} className="flex flex-col gap-3 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div className="font-medium">{r.name}</div>
                  <div className="text-xs text-muted">{[r.position, r.branch, r.hire_date && formatDate(r.hire_date, i18n.language)].filter(Boolean).join(' · ')}</div>
                </div>
                <Badge tone={r.status === 'order_ready' ? 'success' : 'warning'}>{t(`onboarding.kadr.status.${r.status}`)}</Badge>
              </div>
              {r.docs_note && <p className="text-xs text-muted">{r.docs_note}</p>}
              {r.order_no && <p className="text-xs text-muted">№{r.order_no}</p>}
              {r.status !== 'order_ready' && (
                <div className="flex flex-wrap items-center gap-2">
                  <Input value={text[r.employee_id] ?? ''} onChange={(e) => setText({ ...text, [r.employee_id]: e.target.value })} maxLength={r.status === 'waiting_docs' ? 1000 : 40} placeholder={r.status === 'waiting_docs' ? t('onboarding.kadr.docsNote') : t('onboarding.kadr.orderNo')} aria-label={r.name} className="max-w-sm" />
                  <Button
                    disabled={act.isPending}
                    onClick={() =>
                      act.mutate(r.status === 'waiting_docs' ? { id: r.employee_id, path: 'docs', body: { note: text[r.employee_id] || null } } : { id: r.employee_id, path: 'order', body: { order_no: text[r.employee_id] || null } })
                    }
                  >
                    {r.status === 'waiting_docs' ? t('onboarding.kadr.docsDone') : t('onboarding.kadr.orderDone')}
                  </Button>
                </div>
              )}
            </Card>
          ))}
          {q.data.length === 0 && <Card className="p-8 text-center text-muted">{t('common.empty')}</Card>}
          {act.isError && <p role="alert" className="text-sm text-danger">{errorText(t, act.error)}</p>}
        </div>
      )}
    </div>
  )
}
