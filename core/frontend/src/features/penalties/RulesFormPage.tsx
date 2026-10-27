import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, send } from '../../lib/api'
import { errorText } from '../auth/errorText'
import { RulesView } from './RulesView'
import { AUTO_TYPES, type RuleVersion, type RulesConfig, type RulesOverview } from './api'

/** /penalties/rules/new: yangi qoida versiyasi (joriy versiya asosida). Eski jarimalar o'z versiyasida qoladi. */
export function RulesFormPage() {
  const q = useQuery({ queryKey: ['penalties', 'rules'], queryFn: () => api<RulesOverview>('/api/v1/penalties/rules') })
  if (!q.data?.current) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  return <RulesForm base={q.data.current} />
}

function RulesForm({ base }: { base: RuleVersion }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [cfg, setCfg] = useState<RulesConfig>(() => structuredClone(base.config))
  const [note, setNote] = useState('')
  const set = (patch: Partial<RulesConfig>) => setCfg({ ...cfg, ...patch })
  const setStep = (i: number, patch: Partial<RulesConfig['steps'][number]>) => set({ steps: cfg.steps.map((s, j) => (j === i ? { ...s, ...patch } : s)) })
  const setTrigger = (k: (typeof AUTO_TYPES)[number], patch: Partial<RulesConfig['triggers'][typeof k]>) => set({ triggers: { ...cfg.triggers, [k]: { ...cfg.triggers[k], ...patch } } })

  const save = useMutation({
    mutationFn: () => send<RuleVersion>('POST', '/api/v1/penalties/rules', { config: cfg, note: note || null }),
    onSuccess: (v) => {
      void qc.invalidateQueries({ queryKey: ['penalties'] })
      toast.push({ title: t('penalties.rules.saved', { v: v.version }), tone: 'success' })
      navigate('/penalties/rules')
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  const valid = cfg.steps.every((s) => s.label.trim())

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={t('penalties.rules.newVersion')} subtitle={t('penalties.rules.newHint', { v: base.version })} backTo="/penalties/rules" backLabel={t('penalties.rules.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('penalties.rules.triggers')} description={t('penalties.rules.triggersHint')}>
          <ul className="flex flex-col gap-3">
            {AUTO_TYPES.map((k) => (
              <li key={k} className="grid items-center gap-3 sm:grid-cols-[1fr_9rem]">
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" className="size-4" checked={cfg.triggers[k].enabled} onChange={(e) => setTrigger(k, { enabled: e.target.checked })} />
                  {t(`letters.incidents.${k}`)}
                </label>
                {(k === 'late' || k === 'early_leave') && (
                  <Input type="number" min={0} max={600} value={cfg.triggers[k].min_minutes} disabled={!cfg.triggers[k].enabled} onChange={(e) => setTrigger(k, { min_minutes: Number(e.target.value) || 0 })} aria-label={t('penalties.rules.minMinutes')} placeholder={t('penalties.rules.minMinutes')} />
                )}
              </li>
            ))}
          </ul>
        </FormSection>

        <FormSection title={t('penalties.rules.counting')} description={t('penalties.rules.countingHint')}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('penalties.rules.window')} hint={t('penalties.rules.windowHint')}>
              {(id) => <Input id={id} type="number" min={7} max={730} value={cfg.window_days} onChange={(e) => set({ window_days: Number(e.target.value) || 90 })} />}
            </Field>
            <Field label={t('penalties.rules.countMode')}>
              {(id) => (
                <Select id={id} value={cfg.count_mode} onChange={(e) => set({ count_mode: e.target.value as 'all' | 'per_type' })}>
                  <option value="all">{t('penalties.rules.mode.all')}</option>
                  <option value="per_type">{t('penalties.rules.mode.per_type')}</option>
                </Select>
              )}
            </Field>
          </div>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" className="mt-0.5 size-4" checked={cfg.auto_scan} onChange={(e) => set({ auto_scan: e.target.checked })} />
            <span>
              {t('penalties.rules.autoScan')}
              <span className="block text-xs text-muted">{t('penalties.rules.autoScanHint')}</span>
            </span>
          </label>
        </FormSection>

        <FormSection title={t('penalties.rules.steps')} description={t('penalties.rules.stepsHint')}>
          <ol className="flex flex-col gap-4">
            {cfg.steps.map((s, i) => (
              <li key={s.step} className="grid gap-3 rounded-control border border-border p-3 sm:grid-cols-[2rem_1fr_9rem_7rem]">
                <span className="self-center text-lg font-semibold tabular-nums">{s.step}</span>
                <Input value={s.label} onChange={(e) => setStep(i, { label: e.target.value })} maxLength={120} required aria-label={t('penalties.form.label')} placeholder={t('penalties.form.label')} />
                <Input type="number" min={0} step="1000" value={s.amount} onChange={(e) => setStep(i, { amount: Number(e.target.value) || 0 })} aria-label={t('penalties.amount')} placeholder={t('penalties.amount')} />
                <Input type="number" min={0} max={90} value={s.block_days} onChange={(e) => setStep(i, { block_days: Number(e.target.value) || 0 })} aria-label={t('penalties.block')} placeholder={t('penalties.block')} />
              </li>
            ))}
          </ol>
        </FormSection>

        <FormSection title={t('penalties.rules.note')}>
          <Field label={t('penalties.rules.note')} hint={t('penalties.rules.noteHint')}>
            {(id) => <Input id={id} value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} />}
          </Field>
        </FormSection>

        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate('/penalties/rules')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !valid}>
            {t('penalties.rules.saveVersion')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}

/** /penalties/rules/:id: eski versiyani ko'rish. */
export function RuleVersionPage() {
  const { t } = useTranslation()
  const id = Number(useParams().id)
  const q = useQuery({ queryKey: ['penalties', 'rules', id], queryFn: () => api<RuleVersion>(`/api/v1/penalties/rules/${id}`), retry: false })
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <PageHeader title={t('penalties.rules.title')} backTo="/penalties/rules" backLabel={t('penalties.rules.title')} />
      {q.data ? <RulesView version={q.data} /> : <Skeleton className="h-72" />}
    </div>
  )
}
