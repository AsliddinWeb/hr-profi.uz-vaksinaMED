import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, send } from '../../lib/api'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import { addDays, todayLocal } from '../attendance/api'
import { RecruitTabs } from './RecruitTabs'

interface Report {
  items: { recruiter: string | null; calls: number; suitable: number; unsuitable: number; no_answer: number; applications: number; interviews: number; bg_passed: number; offers: number; hired: number }[]
}
const COLS = ['calls', 'suitable', 'unsuitable', 'applications', 'interviews', 'bg_passed', 'offers', 'hired'] as const

/** /recruit/recruiter: qo'ng'iroqlarni qayd etish va rekruter ko'rsatkichlari (deck 23-slayd). */
export function RecruiterPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const manage = useCan()('recruit.manage')
  const [from, setFrom] = useState(() => addDays(todayLocal(), -7))
  const [to, setTo] = useState(todayLocal)
  const [phone, setPhone] = useState('')
  const [outcome, setOutcome] = useState('suitable')
  const q = useQuery({ queryKey: ['recruit', 'recruiter-report', from, to], queryFn: () => api<Report>(`/api/v1/recruit/recruiter-report?start=${from}&end=${to}`) })
  const log = useMutation({
    mutationFn: () => send('POST', '/api/v1/recruit/calls', { outcome, phone: phone || null }),
    onSuccess: () => {
      setPhone('')
      void qc.invalidateQueries({ queryKey: ['recruit', 'recruiter-report'] })
      toast.push({ title: t('pipeline.callSaved'), tone: 'success' })
    },
  })
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader title={t('recruit.title')} subtitle={t('pipeline.recruiterHint')} />
      <RecruitTabs />
      {manage && (
        <Card className="flex flex-wrap items-end gap-3 p-4">
          <Input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+998…" aria-label={t('recruit.candidate.phone')} className="w-48" />
          <Select value={outcome} onChange={(e) => setOutcome(e.target.value)} aria-label={t('pipeline.callOutcome')} className="w-auto">
            {['suitable', 'unsuitable', 'no_answer', 'callback'].map((o) => (
              <option key={o} value={o}>
                {t(`pipeline.call.${o}`)}
              </option>
            ))}
          </Select>
          <Button disabled={log.isPending} onClick={() => log.mutate()}>
            {t('pipeline.callLog')}
          </Button>
          {log.isError && <span role="alert" className="text-sm text-danger">{errorText(t, log.error)}</span>}
        </Card>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <Input type="date" value={from} max={to} onChange={(e) => setFrom(e.target.value)} className="w-auto" aria-label={t('schedule.apply.from')} />
        <Input type="date" value={to} min={from} onChange={(e) => setTo(e.target.value)} className="w-auto" aria-label={t('schedule.apply.to')} />
      </div>
      {!q.data ? (
        <Skeleton className="h-40" />
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs text-muted">
              <tr>
                <th className="px-4 py-2.5 font-medium">{t('recruit.vacancy.recruiter')}</th>
                {COLS.map((c) => (
                  <th key={c} className="px-3 py-2.5 font-medium">
                    {t(`pipeline.col.${c}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {q.data.items.map((r, i) => (
                <tr key={i}>
                  <td className="px-4 py-2.5">{r.recruiter ?? '—'}</td>
                  {COLS.map((c) => (
                    <td key={c} className="px-3 py-2.5 tabular-nums">
                      {r[c]}
                    </td>
                  ))}
                </tr>
              ))}
              {q.data.items.length === 0 && (
                <tr>
                  <td colSpan={COLS.length + 1} className="px-4 py-8 text-center text-muted">
                    {t('common.empty')}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  )
}
