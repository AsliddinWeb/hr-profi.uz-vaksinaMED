import { useMutation } from '@tanstack/react-query'
import { useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Select } from '../../components/ui/Input'
import { upload } from '../../lib/api'
import { errorText } from '../auth/errorText'
import { DATASETS, type Batch, type Dataset } from './api'

/** /migration/new: fayl yuklash (1-qadam). Keyin moslashtirish sahifasiga o'tadi. */
export function NewImportPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [dataset, setDataset] = useState<Dataset>('employees')
  const [file, setFile] = useState<File | null>(null)
  const input = useRef<HTMLInputElement>(null)
  const send = useMutation({
    mutationFn: () => {
      const form = new FormData()
      form.append('file', file as File)
      form.append('dataset', dataset)
      return upload<Batch>('POST', '/api/v1/migration/batches', form)
    },
    onSuccess: (b) => navigate(`/migration/batches/${b.id}`, { replace: true }),
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (file) send.mutate()
  }
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={t('migration.newImport')} subtitle={t('migration.new.subtitle')} backTo="/migration" backLabel={t('migration.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('migration.new.what')}>
          <Field label={t('migration.new.dataset')} hint={t(`migration.new.hint.${dataset}`)}>
            {(id) => (
              <Select id={id} value={dataset} onChange={(e) => setDataset(e.target.value as Dataset)}>
                {DATASETS.map((d) => (
                  <option key={d} value={d}>
                    {t(`migration.dataset.${d}`)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label={t('migration.new.file')} hint={t('migration.new.fileHint')}>
            {(id) => <input ref={input} id={id} type="file" accept=".csv,.txt,.xlsx" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="text-sm" />}
          </Field>
          {dataset === 'attendance' && <p className="text-xs text-muted">{t('migration.new.order')}</p>}
        </FormSection>
        <FormFooter error={send.isError ? errorText(t, send.error) : null}>
          <Button variant="outline" onClick={() => navigate('/migration')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={!file || send.isPending}>
            {send.isPending ? t('migration.uploading') : t('migration.new.next')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
