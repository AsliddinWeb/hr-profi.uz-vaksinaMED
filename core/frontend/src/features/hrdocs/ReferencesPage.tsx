import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileCheck2, FileDown } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { useToast } from '../../components/ui/toastContext'
import { api, send } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { errorText } from '../auth/errorText'
import { EmployeePicker, type Picked } from '../retention/EmployeePicker'

interface ReferenceRow {
  id: number
  number: string
  employee: string
  position: string | null
  department: string | null
  status: 'issued' | 'cancelled'
  issued_at: string
  has_pdf: boolean
  verify_code?: string
}

/** /hr/references: xodim uchun vazifalari kiritilgan va QR bilan tekshiriladigan ma'lumotnoma. */
export function ReferencesPage() {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const [employee, setEmployee] = useState<Picked | null>(null)
  const list = useQuery({ queryKey: ['references'], queryFn: () => api<{ items: ReferenceRow[] }>('/api/v1/references') })
  const issue = useMutation({
    mutationFn: () => send<ReferenceRow>('POST', '/api/v1/references', { employee_id: employee?.id }),
    onSuccess: (doc) => {
      setEmployee(null)
      void qc.invalidateQueries({ queryKey: ['references'] })
      toast.push({ title: t('references.issued', { name: doc.employee }), tone: 'success' })
    },
  })
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader title={t('references.title')} subtitle={t('references.subtitle')} />
      <Card className="flex flex-col gap-4 p-5">
        <div className="flex items-center gap-2 font-semibold"><FileCheck2 className="size-5 text-primary" />{t('references.new')}</div>
        <p className="text-sm text-muted">{t('references.description')}</p>
        <EmployeePicker value={employee} onChange={setEmployee} />
        {issue.isError && <p role="alert" className="text-sm text-danger">{errorText(t, issue.error)}</p>}
        <div><Button disabled={!employee || issue.isPending} onClick={() => issue.mutate()}>{t('references.issue')}</Button></div>
      </Card>
      <div className="flex flex-col gap-3">
        <h2 className="font-semibold">{t('references.recent')}</h2>
        {!list.data ? <Card className="h-24 animate-pulse" /> : list.data.items.map((doc) => (
          <Card key={doc.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
            <div>
              <div className="font-medium">{doc.employee} <span className="text-xs font-normal text-muted">{doc.number}</span></div>
              <div className="text-sm text-muted">{[doc.position, doc.department, formatDateTime(doc.issued_at, i18n.language)].filter(Boolean).join(' · ')}</div>
            </div>
            <div className="flex items-center gap-2">
              <Badge tone={doc.status === 'issued' ? 'success' : 'danger'}>{t(`references.status.${doc.status}`)}</Badge>
              {doc.has_pdf && <a href={`/api/v1/references/${doc.id}/pdf?lang=${i18n.language === 'ru' ? 'ru' : 'uz'}`} download><Button variant="outline"><FileDown className="size-4" />PDF</Button></a>}
            </div>
          </Card>
        ))}
        {list.data?.items.length === 0 && <Card className="p-8 text-center text-muted">{t('common.empty')}</Card>}
      </div>
      <p className="text-xs text-muted">{t('references.verifyHint')}</p>
    </div>
  )
}
