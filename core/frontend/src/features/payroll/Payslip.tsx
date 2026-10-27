import { useTranslation } from 'react-i18next'

import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { RSTATUS_TONE, som, type LineDetail } from './api'

/** Ish haqi varaqasi: hisob-kitob tafsiloti (xodim va HR uchun bir xil ko'rinish). */
export function Payslip({ l }: { l: LineDetail }) {
  const { t } = useTranslation()
  const d = l.details
  const plus: [string, number, string?][] = [
    [t('payroll.line.fixed'), l.fixed, t('payroll.line.fixedHint', { paid: l.paid_days, plan: l.plan_days })],
    [t('payroll.line.commission'), l.commission, t('payroll.line.commissionHint', { sales: som(Number(d.sales)), pct: d.scheme.commission_percent })],
    [t('payroll.line.planBonus'), l.plan_bonus, d.plan !== '0' ? t('payroll.line.planHint', { plan: som(Number(d.plan)) }) : undefined],
    [t('payroll.line.kpiBonus'), l.kpi_bonus, d.kpi_score !== null ? t('payroll.line.kpiHint', { score: d.kpi_score }) : undefined],
    [t('payroll.line.bonus'), l.bonus],
  ]
  const minus: [string, number][] = [
    [t('payroll.line.penalties'), l.penalties],
    [t('payroll.line.deductions'), l.deductions],
    [t('payroll.line.tax', { pct: d.settings.tax_percent }), l.tax],
    [t('payroll.line.inps', { pct: d.settings.inps_percent }), l.inps],
    [t('payroll.line.advance'), l.advance],
  ]
  return (
    <div className="flex flex-col gap-5">
      <Card tint="mint" className="flex flex-wrap items-end justify-between gap-4 p-6">
        <div>
          <div className="text-xs text-muted">{t('payroll.line.toPay')}</div>
          <div className="mt-1 text-3xl font-semibold tabular-nums">{som(l.to_pay)}</div>
        </div>
        <div className="text-right text-sm text-muted">
          <div>{l.period}</div>
          <Badge tone={RSTATUS_TONE[l.status]}>{t(`payroll.status.${l.status}`)}</Badge>
        </div>
      </Card>
      <div className="grid gap-5 md:grid-cols-2">
        <Card className="p-5">
          <h2 className="text-[15px] font-medium">{t('payroll.line.earned')}</h2>
          <dl className="mt-3 flex flex-col gap-2 text-sm">
            {plus.map(([k, v, hint]) => (
              <div key={k}>
                <div className="flex justify-between gap-3">
                  <dt>{k}</dt>
                  <dd className="tabular-nums">{som(v)}</dd>
                </div>
                {hint && v > 0 && <div className="text-xs text-muted">{hint}</div>}
              </div>
            ))}
            <div className="flex justify-between border-t border-border pt-2 font-semibold">
              <dt>{t('payroll.line.gross')}</dt>
              <dd className="tabular-nums">{som(l.gross)}</dd>
            </div>
          </dl>
        </Card>
        <Card className="p-5">
          <h2 className="text-[15px] font-medium">{t('payroll.line.withheld')}</h2>
          <dl className="mt-3 flex flex-col gap-2 text-sm">
            {minus.map(([k, v]) => (
              <div key={k} className="flex justify-between gap-3">
                <dt>{k}</dt>
                <dd className="tabular-nums">{v ? `− ${som(v)}` : '0'}</dd>
              </div>
            ))}
            <div className="flex justify-between border-t border-border pt-2 text-muted">
              <dt>{t('payroll.line.taxable')}</dt>
              <dd className="tabular-nums">{som(l.taxable)}</dd>
            </div>
            <div className="flex justify-between font-semibold">
              <dt>{t('payroll.line.net')}</dt>
              <dd className="tabular-nums">{som(l.net)}</dd>
            </div>
          </dl>
        </Card>
      </div>
      <Card className="p-5 text-sm">
        <h2 className="text-[15px] font-medium">{t('payroll.line.attendance')}</h2>
        <p className="mt-2 text-muted">
          {t('payroll.line.daysInfo', { plan: l.plan_days, paid: l.paid_days, absent: d.absent_days })}
          {d.unpaid_leave_days > 0 && ` · ${t('payroll.line.unpaidLeave', { count: d.unpaid_leave_days })}`}
        </p>
        {l.warnings.length > 0 && (
          <ul className="mt-3 flex flex-wrap gap-2">
            {l.warnings.map((w) => (
              <li key={w}>
                <Badge tone="warning">{t(`payroll.warning.${w}`)}</Badge>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
