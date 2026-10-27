import { Download } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, Navigate, useLocation } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import type { BulkResult } from './api'

/** /employees/bulk-result: ommaviy amal natijasi (yaratilgan hisoblar paroli bilan: faqat bir marta). */
export function BulkResultPage() {
  const { t } = useTranslation()
  const result = (useLocation().state as { result?: BulkResult } | null)?.result
  if (!result) return <Navigate to="/employees" replace />

  const creds = result.results.filter((r) => r.ok && r.login)

  const download = () => {
    // Excel UTF-8 ni to'g'ri ochishi uchun BOM
    const rows = [['F.I.SH', 'Login', 'Vaqtinchalik parol'], ...creds.map((c) => [c.name ?? '', c.login ?? '', c.temp_password ?? ''])]
    const csv = '﻿' + rows.map((r) => r.map((v) => `"${v.replace(/"/g, '""')}"`).join(';')).join('\r\n')
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
    const a = document.createElement('a')
    a.href = url
    a.download = 'xodimlar-loginlari.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <PageHeader title={t('employees.bulkResultTitle')} subtitle={t('employees.bulkResultSummary', { ok: result.succeeded, total: result.total })} />

      {creds.length > 0 && (
        <Card className="p-6">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-muted">{t('users.credentialsHint')}</p>
            <Button variant="outline" onClick={download}>
              <Download className="size-4" />
              {t('employees.downloadLogins')}
            </Button>
          </div>
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-muted">
              <tr>
                <th className="py-2 font-medium">{t('employees.fullName')}</th>
                <th className="py-2 font-medium">{t('auth.login')}</th>
                <th className="py-2 font-medium">{t('auth.password')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border font-mono">
              {creds.map((c) => (
                <tr key={c.id}>
                  <td className="py-2 font-sans">{c.name}</td>
                  <td className="py-2">{c.login}</td>
                  <td className="py-2">{c.temp_password}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      <Card className="p-6">
        <ul className="divide-y divide-border text-sm">
          {result.results.map((r) => (
            <li key={r.id} className="flex items-center gap-3 py-2.5">
              <Badge tone={r.ok ? 'success' : 'danger'}>{r.ok ? t('employees.resultOk') : t('employees.resultFailed')}</Badge>
              <span className="font-medium">{r.name ?? `#${r.id}`}</span>
              {r.error && <span className="text-xs text-muted">{t(`errors.${r.error}`, { defaultValue: r.error })}</span>}
            </li>
          ))}
        </ul>
      </Card>

      <Link to="/employees" className="w-fit">
        <Button>{t('employees.backToList')}</Button>
      </Link>
    </div>
  )
}
