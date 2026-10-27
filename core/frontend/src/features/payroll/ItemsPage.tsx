import { useQuery } from '@tanstack/react-query'
import { Plus, Upload } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input, Select } from '../../components/ui/Input'
import { Pagination } from '../../components/ui/Pagination'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { useCan } from '../auth/useAuth'
import { PayrollTabs } from './PayrollTabs'
import { currentPeriod, KINDS, som, type Item, type Page } from './api'

const SIZE = 30

/** /payroll/items: oylik kiritmalar (savdo, reja, KPI, bonus, avans, ushlanma). */
export function ItemsPage() {
  const { t } = useTranslation()
  const input = useCan()('payroll.input')
  const [period, setPeriod] = useState(currentPeriod())
  const [kind, setKind] = useState('')
  const [text, setText] = useState('')
  const [page, setPage] = useState(1)
  const params = new URLSearchParams({ period, page: String(page), size: String(SIZE) })
  if (kind) params.set('kind', kind)
  if (text.trim()) params.set('q', text.trim())
  const q = useQuery({ queryKey: ['payroll', 'items', params.toString()], queryFn: () => api<Page<Item> & { locked: boolean }>(`/api/v1/payroll/items?${params}`), placeholderData: (p) => p, enabled: /^\d{4}-\d{2}$/.test(period) })
  const locked = q.data?.locked

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <PageHeader
        title={t('payroll.title')}
        subtitle={t('payroll.subtitle')}
        actions={
          input &&
          !locked && (
            <>
              <Link to={`/payroll/items/import?period=${period}`}>
                <Button variant="outline">
                  <Upload className="size-4" />
                  {t('payroll.item.import')}
                </Button>
              </Link>
              <Link to={`/payroll/items/new?period=${period}`}>
                <Button>
                  <Plus className="size-4" />
                  {t('payroll.item.add')}
                </Button>
              </Link>
            </>
          )
        }
      />
      <PayrollTabs />
      <div className="flex flex-wrap items-center gap-3 rounded-card bg-surface p-3 shadow-card">
        <Input type="month" className="w-44" value={period} onChange={(e) => (setPeriod(e.target.value), setPage(1))} aria-label={t('payroll.run.period')} />
        <Select className="w-auto" value={kind} onChange={(e) => (setKind(e.target.value), setPage(1))} aria-label={t('payroll.item.kind')}>
          <option value="">{t('payroll.item.allKinds')}</option>
          {KINDS.map((k) => (
            <option key={k} value={k}>
              {t(`payroll.kind.${k}`)}
            </option>
          ))}
        </Select>
        <Input className="w-48" value={text} onChange={(e) => (setText(e.target.value), setPage(1))} placeholder={t('recruit.candidate.search')} aria-label={t('recruit.candidate.search')} />
        {locked && <Badge tone="warning">{t('payroll.item.locked')}</Badge>}
      </div>
      {!q.data ? (
        <Skeleton className="h-48" />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border text-xs text-muted">
                <tr>
                  <th className="px-5 py-2.5 font-medium">{t('payroll.line.employee')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('payroll.item.kind')}</th>
                  <th className="px-5 py-2.5 text-right font-medium">{t('payroll.item.amount')}</th>
                  <th className="hidden px-5 py-2.5 font-medium md:table-cell">{t('recruit.candidate.note')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border tabular-nums">
                {q.data.items.map((i) => (
                  <tr key={i.id}>
                    <td className="px-5 py-2.5 font-medium">
                      {input && !locked ? (
                        <Link to={`/payroll/items/${i.id}/edit`} className="hover:text-primary hover:underline">
                          {i.employee.name}
                        </Link>
                      ) : (
                        i.employee.name
                      )}
                    </td>
                    <td className="px-5 py-2.5">
                      <Badge tone={i.kind === 'advance' || i.kind === 'deduction' ? 'danger' : i.kind === 'bonus' ? 'success' : 'neutral'}>{t(`payroll.kind.${i.kind}`)}</Badge>
                    </td>
                    <td className="px-5 py-2.5 text-right">{i.kind === 'kpi' ? `${i.amount}%` : som(i.amount)}</td>
                    <td className="hidden px-5 py-2.5 text-muted md:table-cell">{i.note}</td>
                  </tr>
                ))}
                {q.data.items.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-5 py-10 text-center text-muted">
                      {t('common.empty')}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}
      {q.data && q.data.total > SIZE && <Pagination page={page} size={SIZE} total={q.data.total} onPage={setPage} />}
    </div>
  )
}
