import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Download, FileSpreadsheet } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { useToast } from '../../components/ui/toastContext'
import { send, upload } from '../../lib/api'
import { errorText } from '../auth/errorText'
import { formatSize, type DuplicateMatch } from './api'

interface Issue {
  row: number
  status: 'error' | 'duplicate'
  name: string
  errors: { field: string; code: string }[]
  matches: DuplicateMatch[]
  duplicate_of_row: number | null
}

interface Preview {
  token: string
  total: number
  valid: number
  errors: number
  duplicates: number
  unknown_columns: string[]
  issues: Issue[]
}

/** /employees/import: Excel/CSV dan import (avval tekshirish, keyin qo'llash). */
export function ImportPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<Preview | null>(null)

  const check = useMutation({
    mutationFn: (f: File) => {
      const form = new FormData()
      form.append('file', f)
      return upload<Preview>('POST', '/api/v1/employees/import/preview', form)
    },
    onSuccess: setPreview,
  })
  const apply = useMutation({
    mutationFn: () => send<{ created: number; skipped: number }>('POST', '/api/v1/employees/import/apply', { token: preview?.token }),
    onSuccess: async (r) => {
      await qc.invalidateQueries({ queryKey: ['employees'] })
      toast.push({ title: t('employees.importDone', { created: r.created, skipped: r.skipped }), tone: 'success' })
      navigate('/employees')
    },
  })

  const issueText = (i: Issue) => {
    if (i.status === 'duplicate') {
      if (i.duplicate_of_row) return t('employees.dupOfRow', { row: i.duplicate_of_row })
      return i.matches.map((m) => `№${m.employee_no} ${m.full_name} (${m.reasons.map((r) => t(`employees.reason.${r}`)).join(', ')})`).join('; ')
    }
    return i.errors.map((e) => `${t(`employees.importFields.${e.field}`, { defaultValue: e.field })}: ${t(`employees.importErr.${e.code}`, { defaultValue: e.code })}`).join('; ')
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <PageHeader title={t('employees.import')} subtitle={t('employees.importSubtitle')} backTo="/employees" backLabel={t('employees.title')} />

      <FormSection title={t('employees.importStep1')} description={t('employees.importStep1Hint')}>
        <a href="/api/v1/employees/import/template" className="w-fit">
          <Button variant="outline">
            <Download className="size-4" />
            {t('employees.downloadTemplate')}
          </Button>
        </a>
      </FormSection>

      <FormSection title={t('employees.importStep2')}>
        <label className="flex w-fit cursor-pointer items-center gap-2 rounded-control border border-dashed border-border px-4 py-3 text-sm hover:bg-surface-2">
          <FileSpreadsheet className="size-4" />
          {file ? `${file.name} · ${formatSize(file.size)}` : t('employees.chooseExcel')}
          <input
            type="file"
            className="sr-only"
            accept=".xlsx,.csv,.txt"
            onChange={(e) => {
              const f = e.target.files?.[0] ?? null
              setFile(f)
              setPreview(null)
              if (f) check.mutate(f)
            }}
          />
        </label>
        {check.isPending && <p className="text-sm text-muted">{t('employees.checking')}</p>}
        {check.isError && (
          <p role="alert" className="text-sm text-danger">
            {errorText(t, check.error)}
          </p>
        )}
      </FormSection>

      {preview && (
        <>
          <div className="grid gap-4 sm:grid-cols-4">
            <Card tint="lilac" className="p-4">
              <div className="text-xs text-muted">{t('employees.importTotal')}</div>
              <div className="mt-1 text-2xl font-semibold">{preview.total}</div>
            </Card>
            <Card tint="mint" className="p-4">
              <div className="text-xs text-muted">{t('employees.importValid')}</div>
              <div className="mt-1 text-2xl font-semibold">{preview.valid}</div>
            </Card>
            <Card tint="rose" className="p-4">
              <div className="text-xs text-muted">{t('employees.importErrors')}</div>
              <div className="mt-1 text-2xl font-semibold">{preview.errors}</div>
            </Card>
            <Card tint="sand" className="p-4">
              <div className="text-xs text-muted">{t('employees.importDuplicates')}</div>
              <div className="mt-1 text-2xl font-semibold">{preview.duplicates}</div>
            </Card>
          </div>
          {preview.unknown_columns.length > 0 && (
            <p className="text-sm text-muted">
              {t('branches.ignoredColumns')}: {preview.unknown_columns.join(', ')}
            </p>
          )}
          {preview.issues.length > 0 && (
            <FormSection title={t('employees.importIssues')} description={t('employees.importIssuesHint')}>
              <ul className="max-h-96 divide-y divide-border overflow-auto rounded-control border border-border text-sm">
                {preview.issues.map((i) => (
                  <li key={i.row} className="flex gap-3 px-4 py-2.5">
                    <span className="w-12 shrink-0 text-muted">#{i.row}</span>
                    <Badge tone={i.status === 'error' ? 'danger' : 'warning'} className="shrink-0 self-start">
                      {t(`employees.importStatus.${i.status}`)}
                    </Badge>
                    <span className="min-w-0">
                      <b>{i.name}</b>
                      <span className="block text-xs text-muted">{issueText(i)}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </FormSection>
          )}
        </>
      )}

      <FormFooter error={apply.isError ? errorText(t, apply.error) : null}>
        <Button variant="outline" onClick={() => navigate('/employees')}>
          {t('common.cancel')}
        </Button>
        <Button onClick={() => apply.mutate()} disabled={!preview || preview.valid === 0 || apply.isPending}>
          {preview ? t('employees.importApply', { count: preview.valid }) : t('employees.importApplyShort')}
        </Button>
      </FormFooter>
    </div>
  )
}
