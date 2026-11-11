import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ClipboardList, Save } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Field, Input } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { api, send } from '../../lib/api'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import type { PositionRow } from './api'

/** /org/duties: lavozimlarning umumiy vazifalar bazasi va boshqaruv paneli. */
export function PositionDutiesPage() {
  const { t } = useTranslation()
  const canManage = useCan()('org.manage')
  const qc = useQueryClient()
  const positions = useQuery({ queryKey: ['org', 'positions', 'all'], queryFn: () => api<PositionRow[]>('/api/v1/org/positions') })
  const [selected, setSelected] = useState('')
  const [draft, setDraft] = useState('')
  const [filter, setFilter] = useState('')
  const active = useMemo(() => (positions.data ?? []).filter((p) => p.is_active), [positions.data])
  const currentId = Number(selected) || active[0]?.id || 0
  const current = active.find((p) => p.id === currentId)
  const duties = current?.duties ?? []
  useEffect(() => { setDraft(duties.join('\n')) }, [currentId, current?.duties])
  const dirty = draft !== duties.join('\n')
  const save = useMutation({
    mutationFn: () => send('PUT', `/api/v1/org/positions/${currentId}/duties`, { duties: draft.split('\n').map((x) => x.trim()).filter(Boolean) }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ['org', 'positions'] }) },
  })
  const rows = useMemo(() => {
    const q = filter.trim().toLocaleLowerCase()
    return active.filter((p) => !q || `${p.name} ${p.duties?.join(' ') ?? ''}`.toLocaleLowerCase().includes(q))
  }, [active, filter])

  if (!positions.data) return <Skeleton className="mx-auto h-72 max-w-5xl" />
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader title={t('org.dutiesTitle')} subtitle={t('org.dutiesSubtitle')} actions={<Link to="/checklists/control"><Button variant="outline"><ClipboardList className="size-4" />{t('org.dutiesControl')}</Button></Link>} />
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
        <Card className="flex flex-col gap-3 p-4">
          <Input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder={t('org.searchPosition')} aria-label={t('org.searchPosition')} />
          <div className="max-h-[34rem] divide-y divide-border overflow-auto">
            {rows.map((p) => (
              <button key={p.id} type="button" onClick={() => { setSelected(String(p.id)); setDraft((p.duties ?? []).join('\n')) }} className={'w-full rounded-control px-3 py-3 text-left ' + (currentId === p.id ? 'bg-primary/10' : 'hover:bg-surface-2')}>
                <span className="font-medium">{p.name}</span>
                <span className="ml-2 text-xs text-muted">{p.duties?.length ?? 0}</span>
              </button>
            ))}
            {rows.length === 0 && <p className="p-4 text-sm text-muted">{t('common.empty')}</p>}
          </div>
        </Card>
        <Card className="flex flex-col gap-4 p-5">
          {current ? <>
            <div><h2 className="font-semibold">{current.name}</h2><p className="mt-1 text-sm text-muted">{t('org.dutiesEditorHint')}</p></div>
            <Field label={t('org.dutiesLabel')} hint={t('org.dutiesLineHint')}>
              {(id) => <textarea id={id} value={draft} onChange={(e) => setDraft(e.target.value)} rows={14} maxLength={50000} disabled={!canManage} className="w-full rounded-control border border-border bg-surface px-3 py-2 text-sm leading-6 disabled:opacity-70" />}
            </Field>
            {!canManage && <p className="text-xs text-muted">{t('org.dutiesReadOnly')}</p>}
            {save.isError && <p role="alert" className="text-sm text-danger">{errorText(t, save.error)}</p>}
            {canManage && <div className="flex justify-end"><Button disabled={!dirty || save.isPending} onClick={() => save.mutate()}><Save className="size-4" />{t('common.save')}</Button></div>}
          </> : <p className="p-8 text-center text-sm text-muted">{t('org.dutiesNoPosition')}</p>}
        </Card>
      </div>
    </div>
  )
}
