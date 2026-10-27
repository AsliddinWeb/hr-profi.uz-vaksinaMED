import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { formatDateTime } from '../../lib/format'
import { minutesLeft, period, STATUS_TONE, type LeaveRequest } from './api'

/** So'rovlar jadvali (mening so'rovlarim / qaror kutayotganlar / hammasi). */
export function RequestList({ items, showEmployee, now, empty }: { items: LeaveRequest[]; showEmployee?: boolean; now: number; empty: string }) {
  const { t, i18n } = useTranslation()
  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-border text-xs text-muted">
            <tr>
              {showEmployee && <th className="px-5 py-2.5 font-medium">{t('employees.fullName')}</th>}
              <th className="px-5 py-2.5 font-medium">{t('answers.period')}</th>
              <th className="hidden px-5 py-2.5 font-medium md:table-cell">{t('answers.reasonType')}</th>
              <th className="px-5 py-2.5 font-medium">{t('attendance.statusLabel')}</th>
              <th className="hidden px-5 py-2.5 font-medium lg:table-cell">{t('answers.submitted')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {items.map((r) => {
              const left = r.status === 'pending_coordinator' ? minutesLeft(r.escalate_at, now) : null
              return (
                <tr key={r.id}>
                  {showEmployee && (
                    <td className="px-5 py-2.5">
                      <Link to={`/answers/${r.id}`} className="font-medium hover:text-primary hover:underline">
                        {r.employee.full_name}
                      </Link>
                    </td>
                  )}
                  <td className="px-5 py-2.5 tabular-nums">
                    <Link to={`/answers/${r.id}`} className={showEmployee ? '' : 'font-medium hover:text-primary hover:underline'}>
                      {period(r)}
                    </Link>
                    <div className="text-xs text-muted">{t(`answers.kind.${r.kind}`)}</div>
                  </td>
                  <td className="hidden px-5 py-2.5 md:table-cell">{t(`answers.reason.${r.reason_type}`)}</td>
                  <td className="px-5 py-2.5">
                    <Badge tone={STATUS_TONE[r.status]}>{t(`answers.status.${r.status}`)}</Badge>
                    {left !== null && <div className="mt-1 text-xs text-muted">{t('answers.escalatesIn', { time: `${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')}` })}</div>}
                  </td>
                  <td className="hidden px-5 py-2.5 text-muted lg:table-cell">{formatDateTime(r.submitted_at, i18n.language)}</td>
                </tr>
              )
            })}
            {items.length === 0 && (
              <tr>
                <td colSpan={showEmployee ? 5 : 4} className="px-5 py-10 text-center text-muted">
                  {empty}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Card>
  )
}
