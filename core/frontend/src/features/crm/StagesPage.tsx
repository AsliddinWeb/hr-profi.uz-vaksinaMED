import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Zap } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, send } from '../../lib/api'
import { errorText } from '../auth/errorText'
import { KINDS, type Kind, type Stage } from './api'

/** /crm/stages: voronka bosqichlari va avtomatika (bosqichga kirganda qaysi faoliyat necha kunda qo'yiladi). */
export function CrmStagesPage() {
  const { t } = useTranslation()
  const list = useQuery({ queryKey: ['crm', 'stages', 'all'], queryFn: () => api<Stage[]>('/api/v1/crm/stages?all=1') })
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <PageHeader title={t('crm.stages.title')} subtitle={t('crm.stages.subtitle')} />
      {!list.data ? (
        <Skeleton className="h-64" />
      ) : (
        <>
          {list.data.map((s) => (
            <StageRow key={`${s.id}-${s.sort_order}-${s.name}`} stage={s} />
          ))}
          <StageRow stage={null} nextOrder={list.data.length} />
        </>
      )}
    </div>
  )
}

function StageRow({ stage, nextOrder = 0 }: { stage: Stage | null; nextOrder?: number }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const init = stage ?? { name: '', probability: 50, sort_order: nextOrder, is_won: false, auto_activity: '', auto_activity_kind: 'call' as Kind, auto_activity_days: 1, is_active: true }
  const [v, setV] = useState({ ...init, auto_activity: init.auto_activity ?? '' })
  const set = <K extends keyof typeof v>(k: K, val: (typeof v)[K]) => setV((p) => ({ ...p, [k]: val }))
  const save = useMutation({
    mutationFn: () => send(stage ? 'PUT' : 'POST', stage ? `/api/v1/crm/stages/${stage.id}` : '/api/v1/crm/stages', { ...v, auto_activity: v.auto_activity.trim() || null }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['crm'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      if (!stage) setV({ ...init, auto_activity: '', sort_order: nextOrder + 1 })
    },
  })
  return (
    <Card className={'flex flex-col gap-3 p-4 ' + (stage && !stage.is_active ? 'opacity-60' : '')}>
      <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_6rem_5rem_auto] sm:items-end">
        <label className="flex flex-col gap-1 text-xs text-muted">
          {stage ? t('crm.stages.name') : t('crm.stages.newStage')}
          <Input value={v.name} onChange={(e) => set('name', e.target.value)} maxLength={80} placeholder={t('crm.stages.name')} />
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted">
          {t('crm.field.probability')}
          <Input type="number" min={0} max={100} value={v.probability} onChange={(e) => set('probability', Number(e.target.value))} />
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted">
          {t('crm.stages.order')}
          <Input type="number" value={v.sort_order} onChange={(e) => set('sort_order', Number(e.target.value))} />
        </label>
        <div className="flex flex-wrap gap-3 text-sm">
          <label className="inline-flex items-center gap-1.5">
            <input type="checkbox" checked={v.is_won} onChange={(e) => set('is_won', e.target.checked)} />
            {t('crm.stages.isWon')}
          </label>
          {stage && (
            <label className="inline-flex items-center gap-1.5">
              <input type="checkbox" checked={v.is_active} onChange={(e) => set('is_active', e.target.checked)} />
              {t('crm.stages.active')}
            </label>
          )}
        </div>
      </div>
      {!v.is_won && (
        <div className="flex flex-wrap items-center gap-2 rounded-control bg-primary/5 p-2.5 text-sm">
          <Zap className="size-4 text-primary" />
          <span className="text-muted">{t('crm.stages.autoLabel')}</span>
          <Select value={v.auto_activity_kind} onChange={(e) => set('auto_activity_kind', e.target.value as Kind)} aria-label={t('crm.stages.autoKind')} className="w-36">
            {KINDS.map((k) => (
              <option key={k} value={k}>
                {t(`crm.kind.${k}`)}
              </option>
            ))}
          </Select>
          <Input value={v.auto_activity} onChange={(e) => set('auto_activity', e.target.value)} placeholder={t('crm.stages.autoPh')} aria-label={t('crm.stages.autoTitle')} maxLength={160} className="min-w-48 flex-1" />
          <Input type="number" min={0} max={60} value={v.auto_activity_days} onChange={(e) => set('auto_activity_days', Number(e.target.value))} aria-label={t('crm.stages.autoDays')} className="w-20" />
          <span className="text-muted">{t('crm.stages.days')}</span>
        </div>
      )}
      <div className="flex items-center justify-end gap-2">
        {save.isError && <span className="mr-auto text-sm text-danger">{errorText(t, save.error)}</span>}
        <Button variant={stage ? 'outline' : 'primary'} disabled={!v.name.trim() || save.isPending} onClick={() => save.mutate()}>
          {!stage && <Plus className="size-4" />}
          {stage ? t('common.save') : t('crm.stages.add')}
        </Button>
      </div>
    </Card>
  )
}
