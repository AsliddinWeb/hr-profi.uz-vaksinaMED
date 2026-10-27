import { useTranslation } from 'react-i18next'

import { Input, Select } from '../../components/ui/Input'
import { useCan } from '../auth/useAuth'
import { PRIORITIES, type Scope } from './api'
import type { TaskFilter } from './filterState'

/** Topshiriq ko'rinishlari uchun umumiy filtrlar. */
export function Filters({ value, onChange }: { value: TaskFilter; onChange: (f: TaskFilter) => void }) {
  const { t } = useTranslation()
  const can = useCan()
  const all = can('tasks.read') || can('tasks.manage')
  const set = (p: Partial<TaskFilter>) => onChange({ ...value, ...p })
  const scopes: Scope[] = ['mine', 'created', 'watching', ...(all ? (['all'] as const) : [])]
  return (
    <>
      <div className="flex flex-wrap rounded-control bg-(--seg-bg) p-0.5 text-[13px]" role="group" aria-label={t('tasks.scope.label')}>
        {scopes.map((s) => (
          <button key={s} onClick={() => set({ scope: s })} aria-pressed={value.scope === s} className={value.scope === s ? 'rounded-lg bg-(--seg-on) px-3 py-1.5 font-medium text-text shadow-card' : 'rounded-lg px-3 py-1.5 text-muted transition-colors hover:text-text'}>
            {t(`tasks.scope.${s}`)}
          </button>
        ))}
      </div>
      <Input className="min-w-40 flex-1" placeholder={t('tasks.search')} value={value.q} onChange={(e) => set({ q: e.target.value })} aria-label={t('tasks.search')} />
      <Select className="w-auto" value={value.priority} onChange={(e) => set({ priority: e.target.value })} aria-label={t('tasks.priorityLabel')}>
        <option value="">{t('tasks.allPriorities')}</option>
        {PRIORITIES.map((p) => (
          <option key={p} value={p}>
            {t(`tasks.priority.${p}`)}
          </option>
        ))}
      </Select>
      <Input className="w-32" placeholder={t('tasks.label')} value={value.label} onChange={(e) => set({ label: e.target.value })} aria-label={t('tasks.label')} />
    </>
  )
}
