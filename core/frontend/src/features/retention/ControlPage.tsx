import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDate } from '../../lib/format'

type Row = Record<string, string | number | null>
interface Overview {
  total: number
  counts: Record<string, number>
  items: Record<string, Row[]>
  meeting: { last: string | null; due: boolean }
}
const LINKS: Record<string, (r: Row) => string> = {
  interview_overdue: (r) => `/retention/${r.id}`,
  decision_overdue: (r) => `/retention/${r.id}`,
  no_meeting: (r) => `/retention/${r.id}`,
  exit_missing: (r) => `/offboarding/${r.id}`,
  tasks_overdue: (r) => `/tasks/${r.id}`,
  day7_pending: (r) => `/internship/enrollments/${r.id}`,
  vacancies_overdue: (r) => `/recruit/vacancies/${r.id}`,
  attestation_stale: (r) => `/attestation/${r.id}`,
}

/** /control: nazorat paneli (HRD va HR auditor): kechikkan jarayonlar. */
export function ControlPage() {
  const { t, i18n } = useTranslation()
  const q = useQuery({ queryKey: ['control'], queryFn: () => api<Overview>('/api/v1/control/overview'), refetchInterval: 120_000 })
  const d = q.data
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader title={t('control.title')} subtitle={t('control.subtitle')} />
      {!d ? (
        <Skeleton className="h-48" />
      ) : (
        <>
          <Card className="flex flex-wrap items-center gap-3 p-4 text-sm">
            <Badge tone={d.total ? 'danger' : 'success'}>{d.total ? t('control.problems', { n: d.total }) : t('control.allGood')}</Badge>
            <span className="text-muted">
              {t('control.lastMeeting')}: {d.meeting.last ? formatDate(d.meeting.last, i18n.language) : '—'}
            </span>
            {d.meeting.due && <Badge tone="warning">{t('control.meetingDue')}</Badge>}
          </Card>
          {Object.entries(d.items).filter(([, rows]) => rows.length > 0).map(([key, rows]) => (
            <Card key={key} className="flex flex-col gap-2 p-5">
              <h2 className="font-semibold">{t(`control.kind.${key}`)} ({rows.length})</h2>
              <ul className="divide-y divide-border text-sm">
                {rows.map((r, i) => (
                  <li key={i} className="flex flex-wrap items-center justify-between gap-2 py-2">
                    <Link to={LINKS[key](r)} className="font-medium hover:underline">
                      {String(r.employee ?? r.title ?? `#${r.id}`)}
                    </Link>
                    <span className="text-xs text-muted">{r.days !== undefined ? t('control.days', { n: r.days }) : String(r.month ?? r.deadline ?? r.leave_date ?? '')}</span>
                  </li>
                ))}
              </ul>
            </Card>
          ))}
        </>
      )}
    </div>
  )
}
