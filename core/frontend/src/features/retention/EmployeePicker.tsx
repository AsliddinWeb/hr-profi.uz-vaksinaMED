import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '../../components/ui/Button'
import { Field, Input } from '../../components/ui/Input'
import { api } from '../../lib/api'

export interface Picked {
  id: number
  name: string
}

/** Xodimni ism bo'yicha qidirib tanlash (2+ harf). */
export function EmployeePicker({ value, onChange }: { value: Picked | null; onChange: (p: Picked | null) => void }) {
  const { t } = useTranslation()
  const [q, setQ] = useState('')
  const found = useQuery({ queryKey: ['retention', 'emp-search', q], queryFn: () => api<{ items: { id: number; full_name: string }[] }>(`/api/v1/employees?q=${encodeURIComponent(q)}&status=active&size=8`), enabled: q.trim().length >= 2 && !value })
  if (value) {
    return (
      <p className="flex items-center gap-3 text-sm">
        <span className="font-medium">{value.name}</span>
        <Button variant="outline" className="h-8" onClick={() => onChange(null)}>
          {t('common.edit')}
        </Button>
      </p>
    )
  }
  return (
    <>
      <Field label={t('growth.career.search')}>{(id) => <Input id={id} value={q} onChange={(e) => setQ(e.target.value)} />}</Field>
      <ul className="text-sm">
        {found.data?.items.map((e) => (
          <li key={e.id}>
            <button type="button" className="w-full rounded-control px-3 py-2 text-left hover:bg-surface-2" onClick={() => onChange({ id: e.id, name: e.full_name })}>
              {e.full_name}
            </button>
          </li>
        ))}
      </ul>
    </>
  )
}
