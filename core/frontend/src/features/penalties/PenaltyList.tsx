import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { formatDate } from '../../lib/format'
import { money, TONE, type Penalty } from './api'

export function PenaltyList({ items, showEmployee, empty }: { items: Penalty[]; showEmployee: boolean; empty: string }) {
  const { t, i18n } = useTranslation()
  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-border text-xs text-muted">
            <tr>
              <th className="px-5 py-2.5 font-medium">{t('attendance.date')}</th>
              {showEmployee && <th className="px-5 py-2.5 font-medium">{t('employees.fullName')}</th>}
              <th className="px-5 py-2.5 font-medium">{t('penalties.violation')}</th>
              <th className="px-5 py-2.5 font-medium">{t('penalties.measure')}</th>
              <th className="px-5 py-2.5 font-medium">{t('attendance.statusLabel')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {items.map((p) => (
              <tr key={p.id}>
                <td className="px-5 py-2.5 tabular-nums">
                  <Link to={`/penalties/${p.id}`} className="font-medium hover:text-primary hover:underline">
                    {formatDate(p.incident_date, i18n.language)}
                  </Link>
                </td>
                {showEmployee && <td className="px-5 py-2.5">{p.employee.full_name}</td>}
                <td className="px-5 py-2.5">
                  {t(`letters.incidents.${p.incident_type}`)}
                  {p.source === 'manual' && <Badge className="ml-1.5">{t('penalties.manual')}</Badge>}
                </td>
                <td className="px-5 py-2.5">
                  <div>{p.label}</div>
                  <div className="text-xs text-muted tabular-nums">
                    {p.step > 0 && `${t('penalties.stepN', { n: p.step })} · `}
                    {p.amount > 0 ? money(p.amount) : t('penalties.noAmount')}
                    {p.block_days > 0 && ` · ${t('penalties.blockDays', { count: p.block_days })}`}
                  </div>
                </td>
                <td className="px-5 py-2.5">
                  <Badge tone={TONE[p.status]}>{t(`penalties.status.${p.status}`)}</Badge>
                </td>
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
