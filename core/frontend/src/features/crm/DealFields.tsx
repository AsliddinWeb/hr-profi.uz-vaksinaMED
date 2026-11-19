import { useTranslation } from 'react-i18next'

import { Field, Input, Select } from '../../components/ui/Input'
import { MoneyInput } from '../../components/ui/MoneyInput'
import { PersonPicker } from '../tasks/PersonPicker'
import type { Stage } from './api'
import type { DealDraft } from './draft'
import { Stars } from './parts'

/** Bitim maydonlari (yangi bitim va bitim kartasida bir xil). */
export function DealFields({ value, onChange, stages, canAssign, disabled }: { value: DealDraft; onChange: (v: DealDraft) => void; stages?: Stage[]; canAssign: boolean; disabled?: boolean }) {
  const { t } = useTranslation()
  const set = <K extends keyof DealDraft>(k: K, v: DealDraft[K]) => onChange({ ...value, [k]: v })
  return (
    <fieldset disabled={disabled} className="grid gap-4 sm:grid-cols-2">
      <div className="sm:col-span-2">
        <Field label={t('crm.field.title')}>{(id) => <Input id={id} value={value.title} onChange={(e) => set('title', e.target.value)} maxLength={200} required placeholder={t('crm.field.titlePh')} />}</Field>
      </div>
      <Field label={t('crm.field.amount')}>{(id) => <MoneyInput id={id} value={value.amount} onChange={(v) => set('amount', v)} placeholder="0" />}</Field>
      <Field label={t('crm.field.probability')} hint={t('crm.field.probabilityHint')}>
        {(id) => <Input id={id} type="number" min={0} max={100} value={value.probability} onChange={(e) => set('probability', e.target.value)} />}
      </Field>
      <Field label={t('crm.field.company')}>{(id) => <Input id={id} value={value.company ?? ''} onChange={(e) => set('company', e.target.value)} maxLength={160} />}</Field>
      <Field label={t('crm.field.contact')}>{(id) => <Input id={id} value={value.contact_name ?? ''} onChange={(e) => set('contact_name', e.target.value)} maxLength={160} />}</Field>
      <Field label={t('crm.field.phone')}>{(id) => <Input id={id} type="tel" value={value.phone ?? ''} onChange={(e) => set('phone', e.target.value)} maxLength={32} placeholder="+998 90 123 45 67" />}</Field>
      <Field label={t('crm.field.email')}>{(id) => <Input id={id} type="email" value={value.email ?? ''} onChange={(e) => set('email', e.target.value)} maxLength={160} />}</Field>
      <Field label={t('crm.field.expectedClose')}>{(id) => <Input id={id} type="date" value={value.expected_close ?? ''} onChange={(e) => set('expected_close', e.target.value)} />}</Field>
      <Field label={t('crm.field.source')}>{(id) => <Input id={id} value={value.source ?? ''} onChange={(e) => set('source', e.target.value)} maxLength={60} placeholder={t('crm.field.sourcePh')} />}</Field>
      {stages && (
        <Field label={t('crm.field.stage')}>
          {(id) => (
            <Select id={id} value={value.stage_id ?? ''} onChange={(e) => set('stage_id', Number(e.target.value))}>
              {stages.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.probability}%)
                </option>
              ))}
            </Select>
          )}
        </Field>
      )}
      <Field label={t('crm.field.tags')} hint={t('crm.field.tagsHint')}>{(id) => <Input id={id} value={value.tags} onChange={(e) => set('tags', e.target.value)} />}</Field>
      {canAssign && <Field label={t('crm.field.owner')}>{(id) => <PersonPicker id={id} value={value.owner} onChange={(v) => set('owner', v)} />}</Field>}
      <div className="flex flex-col gap-1.5">
        <span className="text-[13px] font-medium">{t('crm.field.priority')}</span>
        <Stars value={value.priority} onChange={disabled ? undefined : (v) => set('priority', v)} />
      </div>
      <div className="sm:col-span-2">
        <Field label={t('crm.field.description')}>
          {(id) => <textarea id={id} value={value.description ?? ''} onChange={(e) => set('description', e.target.value)} rows={3} maxLength={5000} className="w-full rounded-control border border-border bg-surface px-3 py-2 text-[13px]" />}
        </Field>
      </div>
    </fieldset>
  )
}
