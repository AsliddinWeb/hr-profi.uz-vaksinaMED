import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowDown, ArrowUp, Plus, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import type { Item, Template } from './api'

const LIST = '/checklists/templates'
const blank = (): Item => ({ id: '', section: null, text: '', kind: 'yesno', weight: 1, required: true, critical: false })

/** /checklists/templates/new va /checklists/templates/:id/edit */
export function TemplateFormPage() {
  const { id } = useParams()
  const tplId = id ? Number(id) : null
  const q = useQuery({ queryKey: ['checklists', 'template', tplId], queryFn: () => api<Template>(`/api/v1/checklists/templates/${tplId}`), enabled: tplId !== null, retry: false })
  if (tplId === null) return <TemplateForm tpl={null} />
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
  const [name, setName] = useState(tpl?.name ?? '')
  const [description, setDescription] = useState(tpl?.description ?? '')
  const [active, setActive] = useState(tpl?.is_active ?? true)
  const [items, setItems] = useState<Item[]>(tpl?.items?.length ? tpl.items : [blank()])
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const patch = (i: number, p: Partial<Item>) => setItems(items.map((x, j) => (j === i ? { ...x, ...p } : x)))
  const move = (i: number, d: number) => {
    const j = i + d
    if (j < 0 || j >= items.length) return
    const next = [...items]
    ;[next[i], next[j]] = [next[j], next[i]]
    setItems(next)
  }
  const save = useMutation({
    mutationFn: () => {
      const body = { name, description: description || null, is_active: active, items: items.map((x) => ({ ...x, id: x.id || null, section: x.section || null })) }
      return tpl ? send('PUT', `/api/v1/checklists/templates/${tpl.id}`, body) : send('POST', '/api/v1/checklists/templates', body)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['checklists'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(LIST)
    },
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/checklists/templates/${tpl?.id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['checklists'] })
      toast.push({ title: t('checklists.templates.deleted'), tone: 'success' })
      navigate(LIST)
    },
    onError: (e) => setDeleteError(errorText(t, e)),
  })
  const valid = name.trim() && items.length > 0 && items.every((x) => x.text.trim())
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={tpl ? t('checklists.templates.edit') : t('checklists.templates.add')} subtitle={tpl?.name} backTo={LIST} backLabel={t('checklists.templates.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('needs.form.main')}>
          <Field label={t('checklists.templates.name')}>{(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} required maxLength={160} autoFocus />}</Field>
          <Field label={t('needs.form.description')}>{(id) => <Input id={id} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={300} />}</Field>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4" checked={active} onChange={(e) => setActive(e.target.checked)} />
            {t('schedule.activeLabel')}
          </label>
        </FormSection>
        <FormSection title={t('checklists.templates.items')} description={t('checklists.templates.itemsHint')}>
          <ol className="flex flex-col gap-3">
            {items.map((it, i) => (
              <li key={it.id || `n${i}`}>
                <Card tint="sand" className="flex flex-col gap-3 p-4">
                  <div className="flex items-center gap-2">
                    <span className="grid size-7 shrink-0 place-items-center rounded-full bg-surface text-xs font-semibold">{i + 1}</span>
                    <Input value={it.text} onChange={(e) => patch(i, { text: e.target.value })} maxLength={300} placeholder={t('checklists.templates.itemText')} aria-label={t('checklists.templates.itemText')} />
                    <Button variant="ghost" className="h-9 px-2" onClick={() => move(i, -1)} disabled={i === 0} aria-label={t('checklists.templates.up')}>
                      <ArrowUp className="size-4" />
                    </Button>
                    <Button variant="ghost" className="h-9 px-2" onClick={() => move(i, 1)} disabled={i === items.length - 1} aria-label={t('checklists.templates.down')}>
                      <ArrowDown className="size-4" />
                    </Button>
                    <Button variant="ghost" className="h-9 px-2 text-danger" onClick={() => setItems(items.filter((_, j) => j !== i))} disabled={items.length === 1} aria-label={t('common.delete')}>
                      <Trash2 className="size-4" />
                    </Button>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-3">
                    <Input value={it.section ?? ''} onChange={(e) => patch(i, { section: e.target.value })} maxLength={80} placeholder={t('checklists.templates.section')} aria-label={t('checklists.templates.section')} />
                    <Select value={it.kind} onChange={(e) => patch(i, { kind: e.target.value as Item['kind'] })} aria-label={t('checklists.templates.kind')}>
                      <option value="yesno">{t('checklists.templates.yesno')}</option>
                      <option value="score">{t('checklists.templates.score')}</option>
                    </Select>
                    <Input type="number" min={1} max={10} value={it.weight} onChange={(e) => patch(i, { weight: Math.min(10, Math.max(1, Number(e.target.value) || 1)) })} aria-label={t('checklists.templates.weight')} title={t('checklists.templates.weight')} />
                  </div>
                  <div className="flex flex-wrap gap-5 text-sm">
                    <label className="flex items-center gap-2">
                      <input type="checkbox" className="size-4" checked={it.required} onChange={(e) => patch(i, { required: e.target.checked })} />
                      {t('checklists.templates.required')}
                    </label>
                    <label className="flex items-center gap-2">
                      <input type="checkbox" className="size-4" checked={it.critical} onChange={(e) => patch(i, { critical: e.target.checked })} />
                      {t('checklists.critical')}
                    </label>
                  </div>
                </Card>
              </li>
            ))}
          </ol>
          <div>
            <Button variant="outline" onClick={() => setItems([...items, blank()])} disabled={items.length >= 100}>
              <Plus className="size-4" />
              {t('checklists.templates.addItem')}
            </Button>
          </div>
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(LIST)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !valid}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
      {tpl && (
        <FormSection title={t('org.dangerZone')} description={t('checklists.templates.deleteHint')} danger>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              className="text-danger"
              disabled={remove.isPending}
              onClick={async () => {
                if (await confirm({ title: t('checklists.templates.delete'), body: t('org.deleteConfirm', { name: tpl.name }), danger: true, confirmLabel: t('common.delete') })) {
                  setDeleteError(null)
                  remove.mutate()
                }
              }}
            >
              <Trash2 className="size-4" />
              {t('checklists.templates.delete')}
            </Button>
            {deleteError && (
              <span role="alert" className="text-sm text-danger">
                {deleteError}
              </span>
            )}
          </div>
        </FormSection>
      )}
    </div>
  )
}
