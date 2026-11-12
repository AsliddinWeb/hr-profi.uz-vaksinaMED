import { useQueryClient } from '@tanstack/react-query'
import { Building2, FileCheck2, GitBranch, Layers, Network, Plus, Store, Trash2, X } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { useConfirm } from '../../components/ui/confirmContext'
import { Field, Input } from '../../components/ui/Input'
import { useToast } from '../../components/ui/toastContext'
import { send } from '../../lib/api'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import { BranchesPage } from '../branches/BranchesPage'
import { DepartmentsPage } from './DepartmentsPage'
import { OrgStructuresPage } from './OrgStructuresPage'
import { PositionDocsSection } from './PositionDocs'
import { PositionDutiesPage } from './PositionDutiesPage'
import { PositionsPage } from './PositionsPages'
import type { SchemeDept, SchemePos } from './SchemeView'

export type PanelKey = 'node' | 'departments' | 'positions' | 'duties' | 'structures' | 'branches'
export type Selected = { kind: 'dept'; d: SchemeDept } | { kind: 'pos'; p: SchemePos; deptName?: string | null } | null

const TABS: { key: Exclude<PanelKey, 'node'>; icon: typeof Building2 }[] = [
  { key: 'departments', icon: Building2 },
  { key: 'positions', icon: Layers },
  { key: 'duties', icon: FileCheck2 },
  { key: 'structures', icon: Network },
  { key: 'branches', icon: Store },
]

/** Tashkiliy tuzilma ichidagi o'ng panel: tanlangan tugun va Bo'limlar/Lavozimlar/Shajara turlari/Filiallar. Har o'zgarish butun tuzilmani sinxron yangilaydi. */
export function OrgSidePanel({ open, onClose, selected, onSelect }: { open: PanelKey | null; onClose: () => void; selected: Selected; onSelect: (k: PanelKey) => void }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  // panel yopilganda yoki tab almashganda: sxema, ro'yxatlar, filiallar va rekruting birga yangilanadi
  useEffect(() => {
    void qc.invalidateQueries({ queryKey: ['org'] })
    void qc.invalidateQueries({ queryKey: ['branches'] })
  }, [open, qc])
  if (!open) return null
  const body: Record<PanelKey, ReactNode> = {
    node: <NodePanel key={selected ? `${selected.kind}${selected.kind === 'dept' ? selected.d.id : selected.p.id}` : 'none'} selected={selected} onDone={onClose} />,
    departments: <DepartmentsPage />,
    positions: <PositionsPage />,
    duties: <PositionDutiesPage />,
    structures: <OrgStructuresPage />,
    branches: <BranchesPage />,
  }
  return (
    <>
      <button type="button" aria-label={t('common.close')} className="fixed inset-0 z-40 bg-black/20" onClick={onClose} />
      <aside className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[min(860px,100vw)] flex-col bg-bg shadow-pop">
        <div className="flex flex-wrap items-center gap-1 border-b border-border bg-surface px-3 py-2">
          {selected && (
            <PanelTab on={open === 'node'} onClick={() => onSelect('node')} icon={GitBranch}>
              {selected.kind === 'dept' ? selected.d.name : selected.p.name}
            </PanelTab>
          )}
          {TABS.map(({ key, icon }) => (
            <PanelTab key={key} on={open === key} onClick={() => onSelect(key)} icon={icon}>
              {t(`org.panel.${key}`)}
            </PanelTab>
          ))}
          <span className="flex-1" />
          <Button variant="ghost" className="h-8 px-2" aria-label={t('common.close')} onClick={onClose}>
            <X className="size-4" />
          </Button>
        </div>
        <div className="flex-1 overflow-auto p-4">{body[open]}</div>
      </aside>
    </>
  )
}

function PanelTab({ on, onClick, icon: Icon, children }: { on: boolean; onClick: () => void; icon: typeof Building2; children: ReactNode }) {
  return (
    <button type="button" onClick={onClick} className={`inline-flex h-8 max-w-56 items-center gap-1.5 truncate rounded-lg px-3 text-[13px] ${on ? 'bg-primary text-primary-fg' : 'text-muted hover:bg-surface-2 hover:text-text'}`}>
      <Icon className="size-3.5 shrink-0" />
      <span className="truncate">{children}</span>
    </button>
  )
}

/** Tanlangan bo'lim yoki lavozim kartasi: nomini o'zgartirish, ostiga qo'shish, o'chirish, to'liq tahrirlash va lavozim profili. */
function NodePanel({ selected, onDone }: { selected: Selected; onDone: () => void }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const manage = useCan()('org.manage')
  const [name, setName] = useState(selected ? (selected.kind === 'dept' ? selected.d.name : selected.p.name) : '')
  const [slots, setSlots] = useState(selected?.kind === 'pos' ? selected.p.slots : 1)
  const [child, setChild] = useState('')
  const [busy, setBusy] = useState(false)
  if (!selected) return null
  const sync = () => {
    for (const k of ['org', 'branches', 'recruit', 'employees']) void qc.invalidateQueries({ queryKey: [k] })
  }
  const run = async (fn: () => Promise<unknown>, ok: string) => {
    setBusy(true)
    try {
      await fn()
      toast.push({ title: ok, tone: 'success' })
      sync()
      return true
    } catch (e) {
      toast.push({ title: errorText(t, e), tone: 'danger' })
      return false
    } finally {
      setBusy(false)
    }
  }
  const isDept = selected.kind === 'dept'
  const id = isDept ? selected.d.id : selected.p.id
  const deptId = isDept ? selected.d.id : selected.p.department_id
  const save = () =>
    run(() => send('PATCH', isDept ? `/api/v1/org/departments/${id}` : `/api/v1/org/positions/${id}`, isDept ? { name } : { name, slots }), t('common.saved'))
  const add = (kind: 'dept' | 'pos') =>
    child.trim() &&
    run(
      () =>
        kind === 'dept'
          ? send('POST', '/api/v1/org/departments', { name: child.trim(), parent_id: deptId, reports_to_position_id: isDept ? null : id, create_default_positions: true })
          : send('POST', '/api/v1/org/positions', { name: child.trim(), department_id: deptId, parent_id: isDept ? null : id, slots: 1 }),
      t(kind === 'dept' ? 'scheme.deptAdded' : 'scheme.posAdded', { name: child.trim() }),
    ).then((ok) => ok && setChild(''))
  const remove = async () => {
    if (!(await confirm({ title: t('common.delete'), body: t(isDept ? 'scheme.removeDeptQ' : 'scheme.removePosQ', { name: isDept ? selected.d.name : selected.p.name }), danger: true, confirmLabel: t('common.delete') }))) return
    if (await run(() => send('DELETE', isDept ? `/api/v1/org/departments/${id}?detach=true` : `/api/v1/org/positions/${id}`), t('org.deleted'))) onDone()
  }
  return (
    <div className="flex flex-col gap-4">
      <Card className="flex flex-col gap-2 p-5">
        <div className="flex items-center gap-2">
          <Badge tone="info">{t(isDept ? 'org.panel.dept' : 'org.panel.pos')}</Badge>
          {!isDept && selected.deptName && <span className="text-sm text-muted">{selected.deptName}</span>}
        </div>
        <div className="text-lg font-semibold">{isDept ? selected.d.name : selected.p.name}</div>
        {isDept ? (
          <div className="text-sm text-muted">{t('scheme.peopleN', { n: selected.d.headcount })}</div>
        ) : (
          <div className="flex flex-col gap-1 text-sm">
            <span className="text-muted">{t('scheme.slots', { busy: selected.p.occupants.length, total: selected.p.slots })}</span>
            {selected.p.occupants.map((o, i) => (
              <span key={o.id ?? i}>• {o.id ? <Link to={`/employees/${o.id}`} className="text-primary hover:underline">{o.full_name}</Link> : o.full_name}</span>
            ))}
          </div>
        )}
        <div className="mt-1 flex flex-wrap gap-2">
          <Link to={isDept ? `/org/departments/${id}/edit` : `/org/positions/${id}/edit`}>
            <Button variant="outline" className="h-8">{t('org.panel.fullEdit')}</Button>
          </Link>
          {!isDept && (
            <Link to="/recruit/profiles">
              <Button variant="outline" className="h-8">
                <FileCheck2 className="size-4" />
                {t('org.panel.profile')}
              </Button>
            </Link>
          )}
        </div>
      </Card>
      {manage && (
        <>
          <Card className="flex flex-col gap-3 p-5">
            <div className="font-medium">{t('common.edit')}</div>
            <div className="grid gap-3 sm:grid-cols-[1fr_120px]">
              <Field label={t('org.panel.name')}>{(fid) => <Input id={fid} value={name} onChange={(e) => setName(e.target.value)} maxLength={120} />}</Field>
              {!isDept && <Field label={t('org.panel.slots')}>{(fid) => <Input id={fid} type="number" min={0} max={1000} value={slots} onChange={(e) => setSlots(Number(e.target.value))} />}</Field>}
            </div>
            <Button className="w-fit" disabled={busy || !name.trim()} onClick={() => void save()}>
              {t('common.save')}
            </Button>
          </Card>
          <Card className="flex flex-col gap-3 p-5">
            <div className="font-medium">{t('org.panel.addUnder')}</div>
            <Input value={child} onChange={(e) => setChild(e.target.value)} placeholder={t('org.panel.newName')} aria-label={t('org.panel.newName')} maxLength={120} />
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" disabled={busy || !child.trim()} onClick={() => void add('pos')}>
                <Plus className="size-4" />
                {t(isDept ? 'scheme.addPos' : 'scheme.addSubPos')}
              </Button>
              <Button variant="outline" disabled={busy || !child.trim()} onClick={() => void add('dept')}>
                <Plus className="size-4" />
                {t(isDept ? 'scheme.addSubDept' : 'scheme.addDeptUnderPos')}
              </Button>
            </div>
            <div className="text-xs text-muted">{t('org.panel.addHint')}</div>
          </Card>
          {!isDept && <PositionDocsSection positionId={id} />}
          <Card className="flex items-center justify-between gap-3 p-5">
            <div className="text-sm text-muted">{t(isDept ? 'org.panel.deleteDeptHint' : 'org.panel.deletePosHint')}</div>
            <Button variant="outline" className="text-danger" disabled={busy} onClick={() => void remove()}>
              <Trash2 className="size-4" />
              {t('common.delete')}
            </Button>
          </Card>
        </>
      )}
    </div>
  )
}
