import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText, fieldErrors } from '../auth/errorText'
import { DATASETS, FIELDS, MATCH_BY, type Dataset, type Template } from './api'

const LIST = '/migration/templates'

/** /migration/templates/new va /migration/templates/:id/edit. Yangi shablonni moslashtirish sahifasidan (?dataset=&mapping=) to'ldirib ochish mumkin. */
export function TemplateFormPage() {
  const { id } = useParams()
  const tid = id ? Number(id) : null
  const q = useQuery({ queryKey: ['migration', 'template', tid], queryFn: () => api<Template>(`/api/v1/migration/templates/${tid}`), enabled: tid !== null, retry: false })
  if (tid === null) return <TemplateForm tpl={null} />
  if (q.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!q.data) return null
  return <TemplateForm key={q.data.id} tpl={q.data} />
}

function TemplateForm({ tpl }: { tpl: Template | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const [sp] = useSearchParams()
  const preset = (() => {
    try {
      return JSON.parse(sp.get('mapping') ?? '{}') as Record<string, string>
    } catch {
      return {}
    }
  })()
  const [name, setName] = useState(tpl?.name ?? '')
  const [dataset, setDataset] = useState<Dataset>(tpl?.dataset ?? (sp.get('dataset') === 'attendance' ? 'attendance' : 'employees'))
  const [mapping, setMapping] = useState<Record<string, string>>(tpl?.mapping ?? preset)
  const [createMissing, setCreateMissing] = useState(Boolean(tpl?.options?.create_missing))
  const [matchBy, setMatchBy] = useState(tpl?.options?.match_by ?? 'legacy_id')
  const save = useMutation({
    mutationFn: () => {
      const clean = Object.fromEntries(Object.entries(mapping).filter(([k, v]) => v.trim() && FIELDS[dataset].some((f) => f.key === k)))
      const body = { name, dataset, mapping: clean, options: dataset === 'employees' ? { create_missing: createMissing } : { match_by: matchBy } }
      return tpl ? send('PUT', `/api/v1/migration/templates/${tpl.id}`, body) : send('POST', '/api/v1/migration/templates', body)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['migration'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(LIST)
    },
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/migration/templates/${tpl?.id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['migration'] })
      navigate(LIST)
    },
  })
  const fe = save.isError ? fieldErrors(t, save.error) : {}
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={tpl ? t('migration.tpl.edit') : t('migration.tpl.add')} subtitle={tpl?.name} backTo={LIST} backLabel={t('migration.tabs.templates')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('migration.tpl.main')} description={t('migration.tpl.hint')}>
          <Field label={t('migration.tpl.name')} error={fe.name}>{(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} autoFocus />}</Field>
          <Field label={t('migration.new.dataset')}>
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
          <div className="grid gap-3 sm:grid-cols-2">
            {FIELDS[dataset].map((f) => (
              <Field key={f.key} label={t(`migration.field.${f.key}`)} hint={t('migration.tpl.columnHint')}>
                {(id) => <Input id={id} value={mapping[f.key] ?? ''} onChange={(e) => setMapping({ ...mapping, [f.key]: e.target.value })} placeholder="—" />}
              </Field>
            ))}
          </div>
          {dataset === 'employees' ? (
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="size-4" checked={createMissing} onChange={(e) => setCreateMissing(e.target.checked)} />
              {t('migration.createMissing')}
            </label>
          ) : (
            <Field label={t('migration.matchBy')}>
              {(id) => (
                <Select id={id} value={matchBy} onChange={(e) => setMatchBy(e.target.value)}>
                  {MATCH_BY.map((m) => (
                    <option key={m} value={m}>
                      {t(`migration.match.${m}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          )}
        </FormSection>
        <FormFooter error={save.isError && !Object.keys(fe).length ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(LIST)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !name.trim()}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
      {tpl && (
        <FormSection title={t('org.dangerZone')} danger>
          <Button
            variant="outline"
            className="w-fit text-danger"
            disabled={remove.isPending}
            onClick={async () => {
              if (await confirm({ title: t('migration.tpl.delete'), body: tpl.name, danger: true, confirmLabel: t('common.delete') })) remove.mutate()
            }}
          >
            <Trash2 className="size-4" />
            {t('migration.tpl.delete')}
          </Button>
        </FormSection>
      )}
    </div>
  )
}
