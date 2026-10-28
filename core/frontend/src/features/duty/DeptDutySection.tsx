import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { FormSection } from '../../components/ui/Form'
import { api } from '../../lib/api'
import { useCan } from '../auth/useAuth'
import type { DutyTemplate } from './api'

/** Bo'lim sahifasida: shu bo'lim va uning lavozimlari uchun ish chek-listlari (qo'shish havolalari bilan). */
export function DeptDutySection({ deptId }: { deptId: number }) {
  const { t } = useTranslation()
  const can = useCan()
  const allowed = can('duty.read') || can('duty.manage') || can('duty.control')
  const list = useQuery({ queryKey: ['duty', 'templates', 'dept', deptId], queryFn: () => api<DutyTemplate[]>(`/api/v1/duty/templates?department_id=${deptId}`), enabled: allowed, retry: false })
  const positions = useQuery({ queryKey: ['org', 'positions', deptId], queryFn: () => api<{ id: number; name: string }[]>(`/api/v1/org/positions?department_id=${deptId}`), enabled: allowed })
  if (!allowed) return null
  const manage = can('duty.manage')
  const byPos = new Map<number, DutyTemplate[]>()
  for (const c of list.data ?? []) if (c.position_id) byPos.set(c.position_id, [...(byPos.get(c.position_id) ?? []), c])
  const deptLevel = (list.data ?? []).filter((c) => c.scope === 'department')
  const row = (c: DutyTemplate) => (
    <li key={c.id}>
      <Link to={`/checklists/duty/${c.id}/edit`} className="flex items-center justify-between gap-2 rounded-control border border-border px-3 py-2 text-sm hover:bg-surface-2">
        <span>{c.name}</span>
        <span className="flex items-center gap-2 text-xs text-muted">
          {t(`duty.freq.${c.frequency}`)} · {t('duty.points', { n: c.item_count })}
          {!c.is_active && <Badge>{t('duty.inactive')}</Badge>}
        </span>
      </Link>
    </li>
  )
  return (
    <FormSection title={t('duty.deptSection')} description={t('duty.deptSectionHint')}>
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">{t('duty.scope.department')}</h3>
        {manage && (
          <Link to={`/checklists/duty/new?department=${deptId}`}>
            <Button variant="outline" className="h-9">
              <Plus className="size-4" />
              {t('duty.add')}
            </Button>
          </Link>
        )}
      </div>
      <ul className="flex flex-col gap-2">{deptLevel.length ? deptLevel.map(row) : <li className="text-sm text-muted">{t('duty.none')}</li>}</ul>
      {positions.data?.map((p) => (
        <div key={p.id} className="flex flex-col gap-2">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold">
              {t('duty.scope.position')}: {p.name}
            </h3>
            {manage && (
              <Link to={`/checklists/duty/new?position=${p.id}`} aria-label={`${t('duty.add')}: ${p.name}`}>
                <Button variant="ghost" className="h-8 px-2">
                  <Plus className="size-4" />
                </Button>
              </Link>
            )}
          </div>
          <ul className="flex flex-col gap-2">{byPos.get(p.id)?.map(row)}</ul>
        </div>
      ))}
    </FormSection>
  )
}
