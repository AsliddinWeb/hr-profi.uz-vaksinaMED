import type { DealInput, Person } from './api'

/** Forma holati: raqamlar matn ko'rinishida, teglar vergul bilan, mas'ul — tanlangan shaxs. */
export interface DealDraft extends Omit<DealInput, 'amount' | 'probability' | 'tags'> {
  amount: string
  probability: string
  tags: string
  owner: Person[]
}

export const emptyDraft = (stage: number | null = null): DealDraft => ({
  title: '', company: null, contact_name: null, phone: null, email: null, amount: '', probability: '', priority: 0, tags: '', source: null,
  description: null, expected_close: null, stage_id: stage, owner_id: null, owner: [],
}) // prettier-ignore

export function toInput(d: DealDraft): DealInput {
  const s = (v: string | null) => (v && v.trim() ? v.trim() : null)
  return {
    title: d.title.trim(), company: s(d.company), contact_name: s(d.contact_name), phone: s(d.phone), email: s(d.email), amount: Number(d.amount) || 0,
    probability: d.probability === '' ? null : Math.max(0, Math.min(100, Number(d.probability))), priority: d.priority,
    tags: d.tags.split(',').map((x) => x.trim()).filter(Boolean), source: s(d.source), description: s(d.description),
    expected_close: d.expected_close || null, stage_id: d.stage_id, owner_id: d.owner[0]?.id ?? null,
  } // prettier-ignore
}
