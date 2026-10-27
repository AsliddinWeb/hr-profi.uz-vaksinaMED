import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Upload } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { useToast } from '../../components/ui/toastContext'
import { send } from '../../lib/api'
import { errorText } from '../auth/errorText'
import type { BulkResult } from './api'
import { parseBranchCsv } from './csv'

/** /branches/import: CSV dan ommaviy import (avval tekshirish, keyin qo'llash). */
export function BranchImportPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [text, setText] = useState('')
  const parsed = useMemo(() => parseBranchCsv(text), [text])
  const [preview, setPreview] = useState<BulkResult | null>(null)

  const run = useMutation({
    mutationFn: (dry: boolean) => send<BulkResult>('POST', '/api/v1/branches/bulk', { rows: parsed.rows, dry_run: dry }),
    onSuccess: (r, dry) => {
      setPreview(r)
      if (!dry && r.applied) {
        void qc.invalidateQueries({ queryKey: ['branches'] })
        toast.push({ title: t('branches.importDone', { created: r.created, updated: r.updated }), tone: 'success' })
        navigate('/branches')
      }
    },
  })

  const ready = preview !== null && preview.errors.length === 0

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={t('branches.import')} subtitle={t('branches.importHint')} backTo="/branches" backLabel={t('branches.title')} />

      <FormSection title={t('branches.importSource')}>
        <label className="inline-flex w-fit cursor-pointer items-center gap-2 rounded-control border border-border px-3 py-2 text-sm hover:bg-surface-2">
          <Upload className="size-4" />
          {t('branches.chooseFile')}
          <input
            type="file"
            accept=".csv,.txt,text/csv"
            className="sr-only"
            onChange={async (e) => {
              const f = e.target.files?.[0]
              if (f) {
                setText(await f.text())
                setPreview(null)
              }
            }}
          />
        </label>
        <textarea
          value={text}
          onChange={(e) => {
            setText(e.target.value)
            setPreview(null)
          }}
          rows={10}
          spellCheck={false}
          aria-label={t('branches.importSource')}
          placeholder={'raqam,nom,tuman,lat,lng\n16,1-gor bolnitsa,Yunusobod,41.36,69.28'}
          className="w-full rounded-control border border-border bg-surface px-3 py-2 font-mono text-xs"
        />
        {text && (
          <p className="text-sm text-muted">
            {t('branches.parsedRows', { count: parsed.rows.length })}
            {parsed.unknownColumns.length > 0 && ` · ${t('branches.ignoredColumns')}: ${parsed.unknownColumns.join(', ')}`}
          </p>
        )}
      </FormSection>

      {preview && (
        <FormSection title={t('branches.checkResult')}>
          {preview.errors.length === 0 ? (
            <p className="text-sm text-success">{t('branches.importOk', { created: preview.created, updated: preview.updated })}</p>
          ) : (
            <>
              <p className="text-sm font-medium text-danger">{t('branches.importErrors', { count: preview.errors.length })}</p>
              <ul className="max-h-64 overflow-auto text-sm text-muted">
                {preview.errors.slice(0, 100).map((e, i) => (
                  <li key={i}>
                    {t('branches.row')} {e.row}: {t(`branches.err.${e.code}`, { defaultValue: e.code })}
                  </li>
                ))}
              </ul>
            </>
          )}
        </FormSection>
      )}

      <FormFooter error={run.isError ? errorText(t, run.error) : null}>
        <Button variant="outline" onClick={() => navigate('/branches')}>
          {t('common.cancel')}
        </Button>
        {ready ? (
          <Button onClick={() => run.mutate(false)} disabled={run.isPending}>
            {t('branches.importApply')}
          </Button>
        ) : (
          <Button onClick={() => run.mutate(true)} disabled={!parsed.rows.length || run.isPending}>
            {t('branches.validate')}
          </Button>
        )}
      </FormFooter>
    </div>
  )
}
