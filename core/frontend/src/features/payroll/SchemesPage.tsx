import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { Pagination } from '../../components/ui/Pagination'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { useCan } from '../auth/useAuth'
import { PayrollTabs } from './PayrollTabs'
import { som, type Page, type Scheme } from './api'

const SIZE = 30

/** /payroll/schemes: xodimlarning ish haqi sxemalari. */
export function SchemesPage() {
  const { t, i18n } = useTranslation()
  const manage = useCan()('payroll.manage')
  const [text, setText] = useState('')
  const [all, setAll] = useState(false)
  const [page, setPage] = useState(1)
  const params = new URLSearchParams({ page: String(page), size: String(SIZE), current: String(!all) })
  if (text.trim()) params.set('q', text.trim())
  const q = useQuery({ queryKey: ['payroll', 'schemes', params.toString()], queryFn: () => api<Page<Scheme>>(`/api/v1/payroll/schemes?${params}`), placeholderData: (p) => p })
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <PageHeader
        title={t('payroll.title')}
        subtitle={t('payroll.subtitle')}
        actions={
          manage && (
            <Link to="/payroll/schemes/new">
              <Button>
                <Plus className="size-4" />
                {t('payroll.scheme.add')}
              </Button>
            </Link>
          )
        }
      />
      <PayrollTabs />
      <div className="flex flex-wrap items-center gap-3 rounded-card bg-surface p-3 shadow-card">
        <Input className="w-56" value={text} onChange={(e) => (setText(e.target.value), setPage(1))} placeholder={t('recruit.candidate.search')} aria-label={t('recruit.candidate.search')} />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" className="size-4" checked={all} onChange={(e) => (setAll(e.target.checked), setPage(1))} />
          {t('payroll.scheme.history')}
        </label>
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
                  <th className="px-5 py-2.5 font-medium">{t('payroll.scheme.from')}</th>
                  <th className="px-5 py-2.5 text-right font-medium">{t('payroll.scheme.fixed')}</th>
                  <th className="hidden px-5 py-2.5 text-right font-medium sm:table-cell">{t('payroll.scheme.commission')}</th>
                  <th className="hidden px-5 py-2.5 text-right font-medium md:table-cell">{t('payroll.scheme.planBonus')}</th>
                  <th className="hidden px-5 py-2.5 text-right font-medium md:table-cell">{t('payroll.scheme.kpi')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border tabular-nums">
                {q.data.items.map((s) => (
                  <tr key={s.id}>
                    <td className="px-5 py-2.5 font-medium">
                      {manage ? (
                        <Link to={`/payroll/schemes/${s.id}/edit`} className="hover:text-primary hover:underline">
                          {s.employee.name}
                        </Link>
                      ) : (
                        s.employee.name
                      )}
                    </td>
                    <td className="px-5 py-2.5 text-muted">{formatDate(s.effective_from, i18n.language)}</td>
                    <td className="px-5 py-2.5 text-right">{som(s.fixed_amount)}</td>
                    <td className="hidden px-5 py-2.5 text-right sm:table-cell">{s.commission_percent}%</td>
                    <td className="hidden px-5 py-2.5 text-right md:table-cell">{som(s.plan_bonus)}</td>
                    <td className="hidden px-5 py-2.5 text-right md:table-cell">{som(s.kpi_amount)}</td>
                  </tr>
                ))}
                {q.data.items.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-5 py-10 text-center text-muted">
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
