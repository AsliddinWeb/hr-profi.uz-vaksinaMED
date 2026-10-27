import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'

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
import { todayLocal } from '../attendance/api'
import { errorText } from '../auth/errorText'
import { KINDS, type DishKind, type Menu } from './api'

interface Row {
  id: number | null
  name: string
  kind: DishKind
  description: string
}
const blank = (): Row => ({ id: null, name: '', kind: 'main', description: '' })

/** /canteen/menus/new[?date=&copy=] va /canteen/menus/:id/edit */
export function MenuFormPage() {
  const { id } = useParams()
  const [sp] = useSearchParams()
  const mid = id ? Number(id) : null
  const src = mid ?? (sp.get('copy') ? Number(sp.get('copy')) : null)
  const q = useQuery({ queryKey: ['canteen', 'menu', src], queryFn: () => api<Menu>(`/api/v1/canteen/menus/${src}`), enabled: src !== null, retry: false })
  if (src === null) return <MenuForm m={null} copyOf={false} />
  if (q.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!q.data) return null
  return <MenuForm key={q.data.id} m={q.data} copyOf={mid === null} />
}

function MenuForm({ m, copyOf }: { m: Menu | null; copyOf: boolean }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const [sp] = useSearchParams()
  const editing = !!m && !copyOf
  const [date, setDate] = useState(editing ? m.menu_date : (sp.get('date') ?? todayLocal()))
  const [note, setNote] = useState(m?.note ?? '')
  const [rows, setRows] = useState<Row[]>(m ? m.dishes.map((d) => ({ id: editing ? d.id : null, name: d.name, kind: d.kind, description: d.description ?? '' })) : [blank()])
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const back = '/canteen/menus'
  const patch = (i: number, p: Partial<Row>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...p } : r)))
  const save = useMutation({
    mutationFn: () => {
      const body = { menu_date: date, note: note || null, dishes: rows.map((r) => ({ id: r.id, name: r.name, kind: r.kind, description: r.description || null })) }
      return editing ? send<Menu>('PUT', `/api/v1/canteen/menus/${m?.id}`, body) : send<Menu>('POST', '/api/v1/canteen/menus', body)
    },
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['canteen'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(`/canteen/menus/${r.id}`, { replace: true })
    },
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/canteen/menus/${m?.id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['canteen'] })
      toast.push({ title: t('canteen.menus.deleted'), tone: 'success' })
      navigate(back, { replace: true })
    },
    onError: (e) => setDeleteError(errorText(t, e)),
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={editing ? t('canteen.menus.edit') : t('canteen.menus.add')} backTo={back} backLabel={t('canteen.menus.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('needs.form.main')}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('canteen.menus.date')}>{(id) => <Input id={id} type="date" value={date} onChange={(e) => setDate(e.target.value)} required />}</Field>
            <Field label={t('recruit.candidate.note')}>{(id) => <Input id={id} value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} />}</Field>
          </div>
        </FormSection>
        <FormSection title={t('canteen.menus.dishes')} description={t('canteen.menus.dishesHint')}>
          <ol className="flex flex-col gap-3">
            {rows.map((r, i) => (
              <li key={r.id ?? `n${i}`}>
                <Card tint="sand" className="flex flex-wrap items-center gap-2 p-3">
                  <span className="grid size-7 shrink-0 place-items-center rounded-full bg-surface text-xs font-semibold">{i + 1}</span>
                  <Input className="min-w-40 flex-1" value={r.name} onChange={(e) => patch(i, { name: e.target.value })} maxLength={160} placeholder={t('canteen.menus.dishName')} aria-label={t('canteen.menus.dishName')} />
                  <Select className="w-36" value={r.kind} onChange={(e) => patch(i, { kind: e.target.value as DishKind })} aria-label={t('canteen.menus.kind')}>
                    {KINDS.map((k) => (
                      <option key={k} value={k}>
                        {t(`canteen.kind.${k}`)}
                      </option>
                    ))}
                  </Select>
                  <Button variant="ghost" className="h-9 px-2 text-danger" disabled={rows.length === 1} onClick={() => setRows(rows.filter((_, j) => j !== i))} aria-label={t('common.delete')}>
                    <Trash2 className="size-4" />
                  </Button>
                </Card>
              </li>
            ))}
          </ol>
          <div>
            <Button variant="outline" disabled={rows.length >= 30} onClick={() => setRows([...rows, blank()])}>
              <Plus className="size-4" />
              {t('canteen.menus.addDish')}
            </Button>
          </div>
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(back)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || rows.some((r) => !r.name.trim())}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
      {editing && m && (
        <FormSection title={t('org.dangerZone')} description={t('canteen.menus.deleteHint')} danger>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              className="text-danger"
              disabled={remove.isPending}
              onClick={async () => {
                if (await confirm({ title: t('canteen.menus.delete'), body: m.menu_date, danger: true, confirmLabel: t('common.delete') })) {
                  setDeleteError(null)
                  remove.mutate()
                }
              }}
            >
              <Trash2 className="size-4" />
              {t('canteen.menus.delete')}
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
