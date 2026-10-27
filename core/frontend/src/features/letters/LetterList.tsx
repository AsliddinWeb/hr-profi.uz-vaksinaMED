import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { formatDate } from '../../lib/format'
import { STATUS_TONE, type Letter } from './api'

export function LetterList({ items, showEmployee, empty }: { items: Letter[]; showEmployee: boolean; empty: string }) {
  const { t, i18n } = useTranslation()
  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-border text-xs text-muted">
            <tr>
              <th className="px-5 py-2.5 font-medium">№</th>
              {showEmployee && <th className="px-5 py-2.5 font-medium">{t('employees.fullName')}</th>}
              <th className="px-5 py-2.5 font-medium">{t('letters.incident')}</th>
              <th className="px-5 py-2.5 font-medium">{t('attendance.statusLabel')}</th>
              <th className="hidden px-5 py-2.5 font-medium md:table-cell">{t('letters.due')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {items.map((l) => (
              <tr key={l.id}>
                <td className="px-5 py-2.5 tabular-nums">
                  <Link to={`/letters/${l.id}`} className="font-medium hover:text-primary hover:underline">
                    {l.number}
                  </Link>
                </td>
                {showEmployee && <td className="px-5 py-2.5">{l.employee.full_name}</td>}
                <td className="px-5 py-2.5">
                  {t(`letters.incidents.${l.incident_type}`)}
                  <div className="text-xs text-muted">{formatDate(l.incident_date, i18n.language)}</div>
                </td>
                <td className="px-5 py-2.5">
                  <Badge tone={STATUS_TONE[l.status]}>{t(`letters.status.${l.status}`)}</Badge>
                  {l.overdue && <Badge className="ml-1.5" tone="danger">{t('letters.overdue')}</Badge>}
                </td>
                <td className="hidden px-5 py-2.5 text-muted md:table-cell">{l.due_date ? formatDate(l.due_date, i18n.language) : '—'}</td>
              </tr>
            ))}
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
